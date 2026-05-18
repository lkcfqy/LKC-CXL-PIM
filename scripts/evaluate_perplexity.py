#!/usr/bin/env python3
"""
Optional language-model perplexity evaluation.

The main thesis evidence is produced by local simulators and fixed-point
attention benchmarks. This script is an optional end-to-end quality hook for
running WikiText-style perplexity when the required model and dataset
dependencies are available.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "paper_assets/data/perplexity_results.json"


def has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def require_package(name: str, purpose: str) -> None:
    if not has_package(name):
        raise RuntimeError(
            f"Missing Python package '{name}' required for {purpose}. "
            f"Install/update the lkcpim environment before running this mode."
        )


def dependency_report() -> dict[str, bool]:
    return {
        name: has_package(name)
        for name in ["torch", "transformers", "datasets", "auto_gptq", "accelerate"]
    }


def torch_dtype_from_arg(torch: Any, dtype: str) -> Any:
    if dtype == "auto":
        return "auto"
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[dtype]


def evaluate_from_input_ids(
    model: Any,
    input_ids: Any,
    max_length: int,
    stride: int,
    show_progress: bool = True,
) -> dict[str, float]:
    import torch

    if max_length <= 1:
        raise ValueError("--max-length must be greater than 1")
    if stride <= 0:
        raise ValueError("--stride must be positive")
    if input_ids.ndim != 2 or input_ids.shape[0] != 1:
        raise ValueError("input_ids must have shape [1, sequence_length]")

    model.eval()
    try:
        device = next(model.parameters()).device
    except StopIteration:
        device = torch.device("cpu")

    seq_len = int(input_ids.size(1))
    if seq_len < 2:
        raise ValueError("Need at least two tokens to evaluate perplexity")

    nlls: list[Any] = []
    prev_end_loc = 0
    windows = range(0, seq_len, stride)

    if show_progress and has_package("tqdm"):
        from tqdm import tqdm

        windows = tqdm(windows, desc="Evaluating PPL", unit="window")

    for begin_loc in windows:
        end_loc = min(begin_loc + max_length, seq_len)
        trg_len = end_loc - prev_end_loc
        if trg_len <= 0:
            continue

        window_ids = input_ids[:, begin_loc:end_loc].to(device)
        target_ids = window_ids.clone()
        target_ids[:, :-trg_len] = -100

        with torch.no_grad():
            outputs = model(window_ids, labels=target_ids)
            neg_log_likelihood = outputs.loss

        if not torch.isfinite(neg_log_likelihood):
            raise RuntimeError("Model returned a non-finite loss")

        nlls.append(neg_log_likelihood * trg_len)
        prev_end_loc = end_loc
        if end_loc >= seq_len:
            break

    if not nlls or prev_end_loc <= 0:
        raise RuntimeError("No evaluation windows were processed")

    total_nll = torch.stack(nlls).sum()
    mean_nll = total_nll / prev_end_loc
    ppl = torch.exp(mean_nll)
    return {
        "perplexity": float(ppl.item()),
        "mean_nll": float(mean_nll.item()),
        "evaluated_tokens": int(prev_end_loc),
        "num_windows": int(len(nlls)),
    }


def load_dataset_text(args: argparse.Namespace) -> list[str]:
    require_package("datasets", "dataset loading")
    from datasets import load_dataset

    dataset = load_dataset(
        args.dataset_name,
        args.dataset_config,
        split=args.dataset_split,
    )
    if args.num_samples is not None:
        dataset = dataset.select(range(min(args.num_samples, len(dataset))))

    if args.text_field not in dataset.column_names:
        raise KeyError(
            f"Dataset field '{args.text_field}' not found. "
            f"Available fields: {', '.join(dataset.column_names)}"
        )

    texts = [row[args.text_field] for row in dataset if row[args.text_field].strip()]
    if not texts:
        raise ValueError("Dataset produced no non-empty text samples")
    return texts


def load_tokenizer_and_model(args: argparse.Namespace) -> tuple[Any, Any, str]:
    require_package("torch", "model execution")
    require_package("transformers", "tokenizer/model loading")

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        args.model,
        trust_remote_code=args.trust_remote_code,
        local_files_only=args.local_files_only,
    )

    loader = args.loader
    if loader == "auto":
        loader = "gptq" if "gptq" in args.model.lower() and has_package("auto_gptq") else "fp16"

    if loader == "gptq":
        require_package("auto_gptq", "GPTQ model loading")
        from auto_gptq import AutoGPTQForCausalLM

        model = AutoGPTQForCausalLM.from_quantized(
            args.model,
            device_map=args.device_map,
            use_safetensors=True,
            trust_remote_code=args.trust_remote_code,
            local_files_only=args.local_files_only,
        )
        model_type = "GPTQ-Int4"
    elif loader == "fp16":
        model = AutoModelForCausalLM.from_pretrained(
            args.model,
            device_map=args.device_map,
            torch_dtype=torch_dtype_from_arg(torch, args.dtype),
            trust_remote_code=args.trust_remote_code,
            local_files_only=args.local_files_only,
        )
        model_type = f"Transformers-{args.dtype}"
    else:
        raise ValueError(f"Unsupported loader: {loader}")

    return tokenizer, model, model_type


def run_real_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    require_package("torch", "perplexity evaluation")
    import torch

    texts = load_dataset_text(args)
    tokenizer, model, model_type = load_tokenizer_and_model(args)
    encodings = tokenizer("\n\n".join(texts), return_tensors="pt")
    metrics = evaluate_from_input_ids(
        model,
        encodings.input_ids,
        max_length=args.max_length,
        stride=args.stride,
        show_progress=not args.no_progress,
    )

    return {
        "_provenance": provenance(args, mode="real"),
        "model": args.model,
        "model_type": model_type,
        "dataset": {
            "name": args.dataset_name,
            "config": args.dataset_config,
            "split": args.dataset_split,
            "text_field": args.text_field,
            "num_samples": args.num_samples,
        },
        "evaluation": {
            "max_length": args.max_length,
            "stride": args.stride,
            "torch_version": torch.__version__,
        },
        "results": metrics,
        "notes": (
            "Lower perplexity is better. Compare against an FP16 or published "
            "baseline generated with the same tokenizer, dataset, max_length, and stride."
        ),
    }


class SyntheticTokenizer:
    vocab_size = 32

    def __call__(self, text: str, return_tensors: str = "pt") -> Any:
        import torch

        tokens = [((ord(ch) + i) % self.vocab_size) for i, ch in enumerate(text)]
        return SimpleNamespace(input_ids=torch.tensor([tokens], dtype=torch.long))


def run_synthetic_smoke(args: argparse.Namespace) -> dict[str, Any]:
    require_package("torch", "synthetic smoke test")
    import torch

    class ToyCausalLM(torch.nn.Module):
        def __init__(self, vocab_size: int = 32) -> None:
            super().__init__()
            self.vocab_size = vocab_size
            self.dummy = torch.nn.Parameter(torch.zeros(()))

        def forward(self, input_ids: Any, labels: Any | None = None) -> Any:
            logits = torch.zeros(
                input_ids.shape[0],
                input_ids.shape[1],
                self.vocab_size,
                device=input_ids.device,
            )
            predicted = (input_ids + 1) % self.vocab_size
            logits.scatter_(2, predicted.unsqueeze(-1), 3.0)
            if labels is None:
                return SimpleNamespace(logits=logits)
            loss = torch.nn.functional.cross_entropy(
                logits.view(-1, self.vocab_size),
                labels.view(-1),
                ignore_index=-100,
            )
            return SimpleNamespace(loss=loss, logits=logits)

    tokenizer = SyntheticTokenizer()
    model = ToyCausalLM(tokenizer.vocab_size)
    text = "LKC-CXL-PIM synthetic smoke test. " * 8
    input_ids = tokenizer(text, return_tensors="pt").input_ids
    metrics = evaluate_from_input_ids(
        model,
        input_ids,
        max_length=min(args.max_length, 64),
        stride=min(args.stride, 32),
        show_progress=False,
    )
    if not math.isfinite(metrics["perplexity"]):
        raise RuntimeError("Synthetic smoke test produced non-finite perplexity")

    return {
        "_provenance": provenance(args, mode="synthetic_smoke"),
        "model": "ToyCausalLM",
        "model_type": "synthetic",
        "dataset": {
            "name": "deterministic synthetic text",
            "num_tokens": int(input_ids.size(1)),
        },
        "evaluation": {
            "max_length": min(args.max_length, 64),
            "stride": min(args.stride, 32),
            "torch_version": torch.__version__,
        },
        "results": metrics,
        "notes": "Smoke test only; this does not represent language-model quality.",
    }


def provenance(args: argparse.Namespace, mode: str) -> dict[str, Any]:
    command_args = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
    }
    return {
        "generated_by": "scripts/evaluate_perplexity.py",
        "mode": mode,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dependencies": dependency_report(),
        "command_args": command_args,
    }


def write_results(results: dict[str, Any], output: Path) -> None:
    output = output if output.is_absolute() else ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w") as f:
        json.dump(results, f, indent=2)
        f.write("\n")
    print(f"Results saved to: {output.relative_to(ROOT) if output.is_relative_to(ROOT) else output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate causal-LM perplexity with provenance.")
    parser.add_argument("--model", type=str, default="Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")
    parser.add_argument("--loader", choices=["auto", "fp16", "gptq"], default="auto")
    parser.add_argument("--device-map", type=str, default="auto")
    parser.add_argument("--dtype", choices=["auto", "float16", "bfloat16", "float32"], default="auto")
    parser.add_argument("--dataset-name", type=str, default="wikitext")
    parser.add_argument("--dataset-config", type=str, default="wikitext-2-raw-v1")
    parser.add_argument("--dataset-split", type=str, default="test")
    parser.add_argument("--text-field", type=str, default="text")
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--stride", type=int, default=512)
    parser.add_argument("--num-samples", type=int, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--synthetic-smoke", action="store_true", help="Run a local toy-model smoke test.")
    parser.add_argument("--check-deps", action="store_true", help="Print dependency availability and exit.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check_deps:
        print(json.dumps(dependency_report(), indent=2))
        return

    if args.synthetic_smoke:
        results = run_synthetic_smoke(args)
    else:
        results = run_real_evaluation(args)

    write_results(results, args.output)
    print(f"Perplexity: {results['results']['perplexity']:.4f}")


if __name__ == "__main__":
    main()
