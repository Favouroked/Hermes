import unittest

from src.processors.processor import Processor


class PlatformUrlTests(unittest.TestCase):
    def test_accepts_supported_platform_urls(self):
        urls = [
            "https://jobs.lever.co/company/role",
            "https://boards.greenhouse.io/company/jobs/123",
            "https://jobs.ashbyhq.com/company/role",
            "https://company.myworkdayjobs.com/en-US/careers/job/123",
            "https://jobs.smartrecruiters.com/company/123",
            "https://jobs.jobvite.com/company/job/123",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertTrue(Processor._validate_url(url))

    def test_accepts_platform_subdomains(self):
        self.assertTrue(Processor._validate_url("https://sub.jobs.lever.co/company/role"))

    def test_rejects_unsupported_or_lookalike_urls(self):
        urls = [
            "https://example.com/jobs/role",
            "https://notlever.co/company/role",
            "https://jobs.lever.co.evil.example/company/role",
            "http://jobs.lever.co/company/role",
            "https://jobs.lever.co",
            "not a url",
        ]

        for url in urls:
            with self.subTest(url=url):
                self.assertFalse(Processor._validate_url(url))


if __name__ == "__main__":
    unittest.main()
