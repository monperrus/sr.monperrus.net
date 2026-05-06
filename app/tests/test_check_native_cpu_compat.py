import unittest

import check_native_cpu_compat as compat


class CpuCompatTests(unittest.TestCase):
    def test_parse_cpu_flags(self):
        flags = compat.parse_cpu_flags(
            "processor\t: 0\n"
            "vendor_id\t: GenuineIntel\n"
            "flags\t\t: fpu sse sse2 avx avx2\n"
        )

        self.assertEqual(flags, {"fpu", "sse", "sse2", "avx", "avx2"})

    def test_detect_instruction_features(self):
        disassembly = """
            0: c5 fc 77              vzeroupper
            4: c4 e2 7d 58 c1        vpbroadcastd ymm0,xmm1
            9: c4 e2 79 98 c1        vfmadd132ps xmm0,xmm0,xmm1
        """

        self.assertEqual(
            compat.detect_instruction_features(disassembly),
            {"avx", "avx2", "fma"},
        )

    def test_find_incompatible_features(self):
        incompatible = compat.find_incompatible_features(
            {"avx", "avx2", "fma"},
            {"avx"},
        )

        self.assertEqual(incompatible, {"avx2", "fma"})


if __name__ == "__main__":
    unittest.main()
