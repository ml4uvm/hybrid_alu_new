import os, csv
from pyuvm import uvm_env, uvm_agent, uvm_sequencer
from pyuvm.s12_uvm_tlm_interfaces import uvm_analysis_export
from tb.components.driver import ALUDriver
from tb.components.monitor import ALUMonitor
from tb.components.scoreboard import ALUScoreboard

#  ML COVERAGE HELPERS
def to_signed(x):
    if x >= 2**31:
        return x - 2**32
    return x


def classify_operand(x):
    x = to_signed(x)

    if x == 0:
        return "ZERO"
    elif x < 0:
        return "NEG"
    elif 0 < x < 10:
        return "SMALL"
    else:
        return "LARGE"


def get_bin(opcode, a, b):
    return (opcode, classify_operand(a), classify_operand(b))


TOTAL_BINS = 8 * 4 * 4
covered_bins = set()

# COVERAGE + CSV LOGGER
class CoverageExport(uvm_analysis_export):

    def build_phase(self):
        self.write = self.write

    def start_of_simulation_phase(self):
        os.makedirs("results", exist_ok=True)
        self.log_file = open("results/coverage_log.csv", "w", newline="")
        self.writer   = csv.writer(self.log_file)

        # 🔥 UPDATED HEADER (added mode)
        self.writer.writerow([
            "opcode", "a_type", "b_type",
            "result", "zero",
            "cov_gain", "gain_label",
            "mode"   # 🔥 NEW
        ])

    def write(self, item):

        current_bin = get_bin(item.opcode, item.a, item.b)

        # coverage before
        old_cov = (len(covered_bins) / TOTAL_BINS) * 100

        # add bin
        covered_bins.add(current_bin)

        # coverage after
        new_cov = (len(covered_bins) / TOTAL_BINS) * 100

        coverage_gain = new_cov - old_cov

        gain_label = 1 if coverage_gain > 0 else 0

        # 🔥 NEW: safely get mode
        mode = getattr(item, "mode", "unknown")

        self.writer.writerow([
            item.opcode,
            classify_operand(item.a),
            classify_operand(item.b),
            item.result,
            item.zero,
            coverage_gain,
            gain_label,
            mode   # 🔥 NEW
        ])

    def final_phase(self):
        self.log_file.close()
        print(f"Coverage: {len(covered_bins)}/{TOTAL_BINS} bins hit")


#  AGENT
class ALUAgent(uvm_agent):

    def build_phase(self):
        self.seqr    = uvm_sequencer("seqr", self)
        self.driver  = ALUDriver("driver", self)
        self.monitor = ALUMonitor("monitor", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.seqr.seq_item_export)


#  ENVIRONMENT
class ALUEnv(uvm_env):

    def build_phase(self):
        self.agent      = ALUAgent("agent", self)
        self.cov_export = CoverageExport("cov_export", self)
        self.scoreboard = ALUScoreboard("scoreboard", self)

    def connect_phase(self):
        # Monitor → Coverage
        self.agent.monitor.ap.connect(self.cov_export)

        # Monitor → Scoreboard
        self.agent.monitor.ap.connect(self.scoreboard.analysis_export)