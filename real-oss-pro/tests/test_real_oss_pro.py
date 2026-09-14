#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M42 测试: 开源商业版门控定位 + patch(合成数据)。"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent  # real-oss-pro/
sys.path.insert(0, str(HERE))

from locate_docuseal_pro import DocuSealLocator  # noqa: E402


def make_docuseal_fixture(root: str) -> None:
    """合成 DocuSeal 结构: lib/ability.rb + 门控 controller。"""
    lib = Path(root) / "lib"
    lib.mkdir(parents=True)
    (lib / "ability.rb").write_text(
        "class Ability\n"
        "  include CanCan::Ability\n"
        "  def initialize(user)\n"
        "    can :manage, Template, account_id: user.account_id\n"
        "    can :manage, :mcp\n"
        "  end\n"
        "end\n"
    )
    ctl = Path(root) / "app" / "controllers"
    ctl.mkdir(parents=True)
    (ctl / "notifications_settings_controller.rb").write_text(
        "def authorize!\n"
        "  return if can?(:manage, :email_reminders)\n"
        "  redirect_back alert: I18n.t('unlock_with_docuseal_pro')\n"
        "end\n"
    )
    (ctl / "templates_dashboard_controller.rb").write_text(
        "def order\n"
        "  if can?(:manage, :countless)\n"
        "    'created_at'\n"
        "  end\n"
        "end\n"
    )


def make_nocodb_fixture(root: str) -> None:
    """合成 NocoDB CE stub。"""
    p = Path(root) / "packages/nocodb/src/helpers"
    p.mkdir(parents=True)
    (p / "lookupSortLimitGate.ts").write_text(
        "export async function isLookupSortLimitLicensed(_ctx): Promise<boolean> {\n"
        "  return false;\n"
        "}\n"
        "export async function assertLookupSortLimitLicensed(ctx): Promise<void> {\n"
        "  NcError.get(ctx).featureNotSupported({ feature: 'LOOKUP_SORT' });\n"
        "}\n"
    )
    svc = Path(root) / "packages/nocodb/src/services"
    svc.mkdir(parents=True)
    (svc / "sorts.service.ts").write_text(
        "import { assertLookupSortLimitLicensed } from '~/helpers/lookupSortLimitGate';\n"
        "export async function createSort(ctx) {\n"
        "  await assertLookupSortLimitLicensed(ctx);\n"
        "}\n"
    )


class TestDocuSeal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="ds-")
        make_docuseal_fixture(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_locate_gated(self):
        loc = DocuSealLocator(self.tmp)
        r = loc.locate_ability()
        self.assertEqual(r["granted_symbols"], ["mcp"])
        pro = loc.diff_pro_vs_free()
        self.assertIn("countless", pro)
        self.assertIn("email_reminders", pro)

    def test_patch_script_adds_can(self):
        """patch 脚本对 fixture 加授权行。"""
        import patch_docuseal_pro as m
        r = m.patch_ability(self.tmp, dry=True)
        self.assertTrue(r["patched"])
        self.assertIn("can :manage, :countless", r["additions"][1])


class TestNocoDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="nc-")
        make_nocodb_fixture(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_locate_ce_stub(self):
        import locate_patch_nocodb as m
        r = m.locate(self.tmp)
        self.assertTrue(r["is_ce_stub"])
        self.assertTrue(any("sorts.service" in c for c in r["consumers"]))

    def test_patch_flips_gate(self):
        import locate_patch_nocodb as m
        p = m.patch(self.tmp, dry=True)
        self.assertTrue(p["patched"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
