"""Exercise the actual publisher shell with real content validation, no remote writes."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import test_digest_contract as fixture
import test_publication_checks as provenance_fixture

REPO=Path(__file__).resolve().parents[1]


class PublisherPathTests(unittest.TestCase):
    def setup_fixture(self, root):
        root=Path(root)
        repo=root/'repo'
        shutil.copytree(REPO/'scripts', repo/'scripts', ignore=shutil.ignore_patterns('__pycache__'))
        (repo/'digests').mkdir()
        run=root/'run'
        run.mkdir()
        provenance_fixture.PublicationChecksTests().fixture(run)
        item=fixture.news_item()
        items=[item]
        cur=fixture.curation_for(items)
        (run/'digest_items.json').write_text(json.dumps(items))
        (run/'curation.json').write_text(json.dumps(cur))
        (run/'rss_items.json').write_text(json.dumps(items))
        manifest=json.loads((run/'gather_manifest.json').read_text())
        # Old input fixture deliberately lacks generation metadata. This is ONLY
        # a --historical-replay dry run, never fabricated current provenance.
        for entry in manifest.values():
            for key in ('generation_id','collected_at','outputs','rc'):
                entry.pop(key)
        (run/'gather_manifest.json').write_text(json.dumps(manifest))
        rendered,text=fixture.RendererContractTests().render(items,cur)
        self.assertEqual(rendered.returncode,0,rendered.stderr)
        digest=repo/'digests/2026-10-06.md'
        digest.write_text(text)
        # External side-effect boundary only: the new validator is NOT replaced.
        # Built-surface checking is separately exercised against real build.py.
        shutil.copytree(REPO/'templates',repo/'templates')
        shutil.copytree(REPO/'tools',repo/'tools')
        shutil.copytree(REPO/'docs/assets',repo/'docs/assets')
        event_log=root/'events.log'
        original=(repo/'scripts/build.py').read_text()
        marker='\nif __name__ == "__main__":'
        self.assertEqual(original.count(marker), 1, 'offline network substitution target must be unique')
        modified=original.replace(marker, marker +
            "\n    validate_links_live = lambda *a, **k: []\n    validate_bluesky_urls = lambda *a, **k: []", 1)
        self.assertNotEqual(modified,original)
        (repo/'scripts/build.py').write_text(modified)
        fakebin=root/'bin'
        fakebin.mkdir()
        git=fakebin/'git'
        git.write_text('#!/bin/sh\ncase "$*" in\n  "branch --show-current") printf "%s\\n" "${TEST_GIT_BRANCH:-feature-validation}";;\n  "status --porcelain") [ -n "${TEST_GIT_STATUS:-}" ] && printf "%s\\n" "$TEST_GIT_STATUS";;\n  "rev-parse --short=10 HEAD") :;;\n  *) printf "%s\\n" "$*" >> "$TEST_GIT_EVENTS";;\nesac\n')
        git.chmod(0o700)
        npx=fakebin/'npx'
        npx.write_text('#!/bin/sh\nexit 0\n')
        npx.chmod(0o700)
        env={**os.environ,'AIG_PYTHON':sys.executable,'PATH':str(fakebin)+os.pathsep+os.environ['PATH'],
             'TEST_GIT_EVENTS':str(event_log),'AIG_RUN_DIR':str(run)}
        return repo,run,digest,event_log,env

    def test_feature_branch_dry_run_passes_then_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            repo,run,digest,events,env=self.setup_fixture(td)
            env["TEST_GIT_STATUS"] = " M scripts/parent-work.py"
            cmd=['bash',str(repo/'scripts/publish.sh'),'2026-10-06','--dry-run','--historical-replay','--run-dir',str(run)]
            clean=subprocess.run(cmd,cwd=td,env=env,text=True,capture_output=True)
            self.assertEqual(clean.returncode,0,clean.stdout+clean.stderr)
            self.assertIn('dry run passed',clean.stdout)
            self.assertFalse(events.exists(),'dry run invoked a Git write')
            original=digest.read_text()
            changed=original.replace('1 stories','99 stories')
            self.assertNotEqual(changed,original)
            digest.write_text(changed)
            invalid=subprocess.run(cmd,cwd=td,env=env,text=True,capture_output=True)
            self.assertNotEqual(invalid.returncode,0,invalid.stdout+invalid.stderr)
            self.assertIn('dashboard',invalid.stderr)
            self.assertFalse(events.exists(),'rejected input invoked a Git write')

    def test_real_dirty_main_refuses_before_git_writes(self):
        with tempfile.TemporaryDirectory() as td:
            repo,run,digest,events,env=self.setup_fixture(td)
            env.update(TEST_GIT_BRANCH="main", TEST_GIT_STATUS=" M scripts/parent-work.py")
            result=subprocess.run(
                ['bash',str(repo/'scripts/publish.sh'),'2026-10-06','--run-dir',str(run)],
                cwd=td,env=env,text=True,capture_output=True,
            )
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('unrelated source change',result.stderr)
            self.assertFalse(events.exists(),'dirty publication invoked a Git write')


if __name__=='__main__':
    unittest.main()
