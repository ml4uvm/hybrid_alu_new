import csv


class MLTestPool:
    """
    Handles ML-prioritized / clustered ALU testcases.

    Loads clustered_tests.csv (output of ml/cluster_tests.py) once and
    exposes the full ranked list. This does NOT cycle indefinitely —
    Phase 1 of the hybrid sequence must exhaust the pool exactly once,
    in descending predicted-gain order, then hand off to gap-filling
    (Phase 2). Replaying already-covered bins forever was the root
    cause of stagnation in the deprecated epsilon-greedy ALU hybrid.
    """

    def __init__(self, file_path):
        self.testcases = self._load_testcases(file_path)
        if not self.testcases:
            raise ValueError("ML pool is empty!")

    # =====================================================
    # Load clustered ALU testcases (already sorted by
    # predicted_gain, descending, from cluster_tests.py)
    # =====================================================
    def _load_testcases(self, file_path):
        testcases = []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                testcase = {
                    "opcode": int(row["opcode"]),
                    "a_type": int(row["a_type"]),
                    "b_type": int(row["b_type"]),
                    "predicted_gain": float(row["predicted_gain"]),
                    "cluster": int(row["cluster"]),
                }
                testcases.append(testcase)
        return testcases

    # =====================================================
    # Return the full ranked pool, run-once, in priority order
    # =====================================================
    def get_all(self):
        return list(self.testcases)

    def __len__(self):
        return len(self.testcases)