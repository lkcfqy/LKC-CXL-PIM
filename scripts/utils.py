from dataclasses import dataclass

@dataclass
class HBM3Config:
    """HBM3 8Gb die organization parameters"""
    channels: int = 1
    pseudochannels: int = 2
    bankgroups: int = 4
    banks_per_bg: int = 4
    rows: int = 32768
    columns: int = 64
    bytes_per_access: int = 64
    
    @property
    def total_banks(self) -> int:
        return self.pseudochannels * self.bankgroups * self.banks_per_bg

def addr_to_hbm_vector(addr: int, hbm: HBM3Config) -> str:
    """Convert physical address to HBM3 address vector string"""
    col = (addr // hbm.bytes_per_access) % hbm.columns
    row = (addr // (hbm.bytes_per_access * hbm.columns)) % hbm.rows
    bank = (addr // (hbm.bytes_per_access * hbm.columns * hbm.rows)) % hbm.total_banks
    
    ch = 0
    pc = bank // (hbm.bankgroups * hbm.banks_per_bg)
    remaining = bank % (hbm.bankgroups * hbm.banks_per_bg)
    bg = remaining // hbm.banks_per_bg
    ba = remaining % hbm.banks_per_bg
    
    return f"{ch},{pc},{bg},{ba},{row},{col}"

def generate_addr_vec(
    hbm: HBM3Config,
    bank_id: int,
    row: int,
    col: int
) -> str:
    """Generate address vector string for trace"""
    ch = 0
    pc = bank_id // (hbm.bankgroups * hbm.banks_per_bg)
    remaining = bank_id % (hbm.bankgroups * hbm.banks_per_bg)
    bg = remaining // hbm.banks_per_bg
    ba = remaining % hbm.banks_per_bg
    
    return f"{ch},{pc},{bg},{ba},{row},{col}"
