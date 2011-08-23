# -*- coding: utf-8 -*-
# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (c) 2010-2011, GEM Foundation.
#
# OpenQuake is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3
# only, as published by the Free Software Foundation.
#
# OpenQuake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License version 3 for more details
# (a copy is included in the LICENSE file that accompanied this code).
#
# You should have received a copy of the GNU Lesser General Public License
# version 3 along with OpenQuake.  If not, see
# <http://www.gnu.org/licenses/lgpl-3.0.txt> for a copy of the LGPLv3 License.


"""
Unit tests for the tools/oqbugs.py tool.
"""

import unittest
from tools.oqbugs import (CommitsOutput, filter_reviewers, filter_bugs,
        launchpad_lookup)
import mock
import os

CACHE_DIR = os.path.expanduser("~/.launchpadlib-test/cache/")


class OqBugsTestCase(unittest.TestCase):
    """Tests the behaviour of ChangeLog custom action."""

    def _prepare_mock(self, bugs):
        bugs_list = {}
        for bug in bugs:
            magic_mock = mock.MagicMock()
            magic_mock.bug_tasks.__getitem__ = mock.Mock(spec=[])
            bugs_list.update({bug : magic_mock})
        return bugs_list

    def setUp(self):
        self.bugs =  {}

        # utilities methods for mocking a dict...
        def getitem(name):
            return self.bugs[name]

        def setitem(name, val):
            self.bugs[name] = val

        self.correct_commits = ['[r=favalex][f=827908]',
                '[r=mbarbon][f=*827366]',
                '[r=favalex][f=819689]', '[r=mbarbon] [f=827256]',
                '[r=larsbutler][f=807360]', '[r=al-maisan] [f=812698]',
                '[r=al-maisan][f=802396]', '[r=favalex][f=817081]',
                '[r=larsbutler][f=809217]', '[r=larsbutler] [f=82464]']

        self.skip_commits = ['[r=mbarbon][f=*827366]']
        self.multiple_bugs_commit = ['[r=mbarbon][f=827366,812698,809217]']
        self.wrong_lines = ['lorem', 'loren', 'sofia']

        self.launchpad = mock.MagicMock()
        self.launchpad.bugs.__setitem__ = mock.Mock(side_effect=setitem)
        self.launchpad.bugs.__getitem__ = mock.Mock(side_effect=getitem)

    def tearDown(self):
        pass

    def test_commits_output_is_empty(self):
        self.assertEquals(CommitsOutput.since('0 week'), [])

    # one month to be sure to have commit lines
    def test_commits_output_for_one_month(self):
        self.assertTrue(len(CommitsOutput.since('1 month')))

    def test_commits_output_reviewers(self):
        for commit in self.correct_commits:
            self.assertTrue(len(filter_reviewers(commit)))

    def test_filter_bugs_multiple(self):
        self.assertEquals(
                len(list(filter_bugs(self.multiple_bugs_commit[0]))), 3)

    def test_filter_bugs_skip(self):
        for commit in self.skip_commits:
            self.assertEquals(len(list(filter_bugs(commit))), 0)

    def test_filter_bugs_wrong_format(self):
        for bug in self.wrong_lines:
            self.assertEquals(filter_bugs(bug), [])

    def test_launchpad_instances(self):
        bugs_list = filter_bugs(self.multiple_bugs_commit[0])
        self.bugs = self._prepare_mock(bugs_list)
        print self.bugs
        self.assertEquals(len(launchpad_lookup(self.launchpad,
                self.bugs.keys())), 3)

    def test_launchpad_attributes(self):
        bugs_list = filter_bugs(self.correct_commits[0])
        self.bugs = self._prepare_mock(bugs_list)
        for bug_instance in launchpad_lookup(self.launchpad, self.bugs.keys()):
            self.assertTrue(isinstance(bug_instance, mock.Mock))
            self.assertTrue(isinstance(bug_instance.bug_tasks, mock.Mock))
            self.assertTrue(isinstance(bug_instance.title, mock.Mock))
            self.assertTrue(isinstance(
                bug_instance.bug_tasks[0].date_fix_committed, mock.Mock))
            self.assertTrue(isinstance(
                bug_instance.bug_tasks[0].assignee.name, mock.Mock))
            self.assertTrue(isinstance(
                bug_instance.bug_tasks[0].web_link, mock.Mock))
            self.assertTrue(False)



    def test_commits_output_bugs(self):
        for commit in self.correct_commits:
            # preparing bugs for mocker
            self.bugs = self._prepare_mock(commit)
            for bug in launchpad_lookup(self.launchpad, self.bugs):
                self.assertTrue(isinstance(bug, mock.Mock))
