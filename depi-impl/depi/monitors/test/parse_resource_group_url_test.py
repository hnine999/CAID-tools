import unittest
import sys

sys.path.append("src")
from depi_monitors.git_monitor import parse_resource_group_url

class TestParseResourceGroupUrl(unittest.TestCase):
    def test_http_url(self):
        result = parse_resource_group_url('http://localhost:3001/patrik/c-sources.git')
        self.assertEqual(result['host'], 'http://localhost:3001')
        self.assertEqual(result['owner'], 'patrik')
        self.assertEqual(result['name'], 'c-sources')
        self.assertEqual(result['host_name'], 'localhost:3001')
        self.assertEqual(result['host_prefix'], 'http://')
        self.assertFalse(result['is_ssh'])

    def test_https_url(self):
        result = parse_resource_group_url('https://git.isis.vanderbilt.edu/aa-caid/depi-impl.git')
        self.assertEqual(result['host'], 'https://git.isis.vanderbilt.edu')
        self.assertEqual(result['owner'], 'aa-caid')
        self.assertEqual(result['name'], 'depi-impl')
        self.assertEqual(result['host_name'], 'git.isis.vanderbilt.edu')
        self.assertEqual(result['host_prefix'], 'https://')
        self.assertFalse(result['is_ssh'])

    def test_ssh_url(self):
        result = parse_resource_group_url('git@git.isis.vanderbilt.edu:aa-caid/depi-impl.git')
        self.assertEqual(result['host'], 'git@git.isis.vanderbilt.edu')
        self.assertEqual(result['owner'], 'aa-caid')
        self.assertEqual(result['name'], 'depi-impl')
        self.assertEqual(result['host_name'], 'git.isis.vanderbilt.edu')
        self.assertEqual(result['host_prefix'], 'git@')
        self.assertTrue(result['is_ssh'])

    def test_ssh_url_with_prefix(self):
        result = parse_resource_group_url('git-vandy:VUISIS/p-state-visualizer.git')
        self.assertEqual(result['host'], 'git-vandy')
        self.assertEqual(result['owner'], 'VUISIS')
        self.assertEqual(result['name'], 'p-state-visualizer')
        self.assertEqual(result['host_name'], 'git-vandy')
        self.assertEqual(result['host_prefix'], '')
        self.assertTrue(result['is_ssh'])

    def test_ssh_url_without_prefix(self):
        result = parse_resource_group_url('git@github.com:webgme/webgme.git')
        self.assertEqual(result['host'], 'git@github.com')
        self.assertEqual(result['owner'], 'webgme')
        self.assertEqual(result['name'], 'webgme')
        self.assertEqual(result['host_name'], 'github.com')
        self.assertEqual(result['host_prefix'], 'git@')
        self.assertTrue(result['is_ssh'])


if __name__ == '__main__':
    unittest.main()
