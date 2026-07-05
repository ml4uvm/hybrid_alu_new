import os
import random
from pyuvm import uvm_sequence
from tb.sequences.sequence_item import ALUSeqItem
from tb.components import env as env_mod  # covered_bins / get_bin / is_coverage_complete
from hybrid.ml_pool import MLTestPool

# Must match env.py's classify_operand() category ordering
OPERAND_TYPES = ["ZERO", "SMALL", "LARGE", "NEG"]
OPCODES = list(range(8))  # 0..7


class ALUSequence(uvm_sequence):
    """
    Hybrid ALU sequence — stateless direct gap synthesis.

    Phase 1 - ML pool: replay offline RF+KMeans clustered testcases once.
    Phase 2 - Gap fill: scan the full (opcode, a_type, b_type) bin space
              in fixed deterministic order and directly synthesize the
              stimulus for each uncovered bin. No preamble or occupancy
              tracking is required — unlike the FIFO hybrid, an ALU bin
              is fully determined by a single transaction, so "cost" is
              uniformly 1 and there is nothing to plan ahead for.
    """

    def __init__(self, name="ALUSequence", total_budget=128, use_hybrid=True):
        super().__init__(name)
        self.total_budget = total_budget
        self.use_hybrid = use_hybrid
        self.executed = 0

    # -----------------------------------------------------------------
    # Stimulus value generation from a type label
    # -----------------------------------------------------------------
    def generate_value(self, operand_type):
        if operand_type == "ZERO":
            return 0
        elif operand_type == "SMALL":
            return random.randint(1, 9)
        elif operand_type == "LARGE":
            return random.randint(10, 100)
        elif operand_type == "NEG":
            return random.randint(-20, -1)
        raise ValueError(f"Unknown operand_type: {operand_type}")

    # -----------------------------------------------------------------
    # Drive a single transaction
    # -----------------------------------------------------------------
    async def drive_item(self, opcode, a_type, b_type, mode):
        item = ALUSeqItem("item")
        item.opcode = opcode
        item.a = self.generate_value(a_type)
        item.b = self.generate_value(b_type)
        item.mode = mode
        await self.start_item(item)
        await self.finish_item(item)
        self.executed += 1

    # -----------------------------------------------------------------
    # Phase 1: ML pool (run once, not cycled)
    # -----------------------------------------------------------------
    async def run_ml_pool(self):
        base_dir = os.path.dirname(__file__)
        csv_path = os.path.join(base_dir, "../../ml/clustered_tests.csv")
        pool = MLTestPool(csv_path)
        reverse_map = {0: "ZERO", 1: "SMALL", 2: "LARGE", 3: "NEG"}

        print(f"[HYBRID] Phase 1: running {len(pool)} ML-prioritized testcases")

        for tc in pool.get_all():
            if self.executed >= self.total_budget:
                return
            if env_mod.is_coverage_complete():
                return
            a_type = reverse_map[tc["a_type"]]
            b_type = reverse_map[tc["b_type"]]
            await self.drive_item(tc["opcode"], a_type, b_type, mode="ml")

        print(f"[HYBRID] Phase 1 done. executed={self.executed}")

    # -----------------------------------------------------------------
    # Phase 2: ordered gap filling — scan bin space in fixed order
    # -----------------------------------------------------------------
    def pick_next_uncovered_bin(self):
        """
        Scan the full (opcode, a_type, b_type) space in fixed
        deterministic order (opcode -> a_type -> b_type) and return
        the first uncovered bin, or None if all bins are covered.

        Unlike the FIFO hybrid's pick_cheapest_gap(), there is no cost
        comparison here: every ALU bin costs exactly one transaction
        with no preamble, so "cheapest" and "next in fixed order" are
        equivalent. Fixed ordering is used (rather than randomized)
        for reproducibility of results reported in the paper.
        """
        covered = env_mod.covered_bins
        for opcode in OPCODES:
            for a_type in OPERAND_TYPES:
                for b_type in OPERAND_TYPES:
                    bin_key = env_mod.get_bin_types(opcode, a_type, b_type)
                    if bin_key not in covered:
                        return (opcode, a_type, b_type)
        return None

    async def run_gap_filling(self):
        remaining = self.total_budget - self.executed
        print(f"[HYBRID] Phase 2: {remaining} testcases remaining in budget")

        while remaining > 0 and not env_mod.is_coverage_complete():
            gap = self.pick_next_uncovered_bin()
            if gap is None:
                print("[HYBRID] No uncovered bins remain.")
                break

            opcode, a_type, b_type = gap
            await self.drive_item(opcode, a_type, b_type, mode="gapfill")
            remaining = self.total_budget - self.executed

        print(f"[HYBRID] Gap filling complete. Total executed: "
              f"{self.executed}/{self.total_budget}")

    # -----------------------------------------------------------------
    # Baseline mode, preserved for CRV/CDV comparison runs
    # -----------------------------------------------------------------
    async def run_baseline(self):
        print(f"[BASELINE MODE] Running {self.total_budget} random tests")
        for _ in range(self.total_budget):
            item = ALUSeqItem("item")
            item.randomize()
            item.mode = "random"
            await self.start_item(item)
            await self.finish_item(item)
            self.executed += 1

    # -----------------------------------------------------------------
    # Entry point
    # -----------------------------------------------------------------
    async def body(self):
        if not self.use_hybrid:
            await self.run_baseline()
            return

        await self.run_ml_pool()
        await self.run_gap_filling()