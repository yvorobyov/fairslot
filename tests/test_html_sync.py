import os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class HtmlSync(unittest.TestCase):
    def test_package_copy_identical(self):
        a = open(os.path.join(ROOT, "fairslot.html"), "rb").read()
        b = open(os.path.join(ROOT, "fairslot", "fairslot.html"), "rb").read()
        self.assertEqual(a, b, "copy fairslot/fairslot.html to keep the pip package in sync")


if __name__ == "__main__":
    unittest.main()
