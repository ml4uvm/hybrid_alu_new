import cocotb
from pyuvm import uvm_test, uvm_root
from tb.components.env import ALUEnv
from tb.sequences.sequence import ALUSequence


class ALUTest(uvm_test):
    def build_phase(self):
        self.env = ALUEnv("env", self)

    async def run_phase(self):
        self.raise_objection()

        # =====================================================
        # BASELINE MODE (CRV/CDV comparison)
        # =====================================================
        seq = ALUSequence("seq", total_budget=512, use_hybrid=False)

        # =====================================================
        # HYBRID MODE (ML pool -> ordered gap filling)
        # Budget matches the offline ALU paper's Table I testcase
        # counts: 128, 192, 256, 384, 512
        # =====================================================
        # seq = ALUSequence("seq", total_budget=512, use_hybrid=True)

        await seq.start(self.env.agent.seqr)
        self.drop_objection()


@cocotb.test()
async def run_test(dut):
    await uvm_root().run_test("ALUTest")