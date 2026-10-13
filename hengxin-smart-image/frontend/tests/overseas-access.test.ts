import assert from "node:assert/strict";
import test from "node:test";
import {
  mayEnter,
  permittedPath,
  previewIdentity,
} from "../src/overseas-preview/access";
test("国内授权不授予海外角色或入口权限", () => {
  const user = previewIdentity("domestic", "designer");
  assert.equal(mayEnter(user, "overseas"), false);
  assert.equal(permittedPath(user, "/overseas/tasks"), "/business");
  assert.equal(mayEnter(user, "domestic"), true);
});
test("海外授权不授予国内权限，未登录始终回登录", () => {
  const user = previewIdentity("overseas", "operator");
  assert.equal(permittedPath(user, "/domestic"), "/business");
  assert.equal(permittedPath(user, "/overseas/create"), "/overseas/create");
  user.authenticated = false;
  assert.equal(permittedPath(user, "/overseas/create"), "/auth/login");
  assert.equal(mayEnter(user, "overseas"), false);
});
test("无权限和双权限入口分别判定", () => {
  for (const business of ["domestic", "overseas"] as const) {
    assert.equal(
      mayEnter(previewIdentity("none", "operator"), business),
      false,
    );
    assert.equal(mayEnter(previewIdentity("both", "designer"), business), true);
  }
});

test("海外管理中心独立校验管理员角色", () => {
  for (const role of ['operator', 'designer'] as const)
    assert.equal(permittedPath(previewIdentity('both', role), '/overseas/management/users'), '/overseas/tasks');
  assert.equal(permittedPath(previewIdentity('both', 'admin'), '/overseas/management/users'), '/overseas/management/users');
  assert.equal(permittedPath(previewIdentity('domestic', 'admin'), '/overseas/management/users'), '/business');
});
