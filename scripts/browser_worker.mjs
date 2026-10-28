const fs = await import("node:fs/promises");
const { createHash } = await import("node:crypto");
const { binding, dryRun, markerPath, day, nowISO, today, nowSeconds } = input;
let task;
let attempted = false;
let controlled = false;
let result;

function hash(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

function fresh(text) {
  if (!text) return false;
  if (/今天|今日|刚刚/.test(text)) return true;
  const [y, m, d] = today;
  if (new RegExp(`${y}[-/.年]0?${m}[-/.月]0?${d}(?:日|\\b)`).test(text)) return true;
  const relative = text.match(/(\d+)\s*(秒|分钟|小时)前/);
  if (!relative) return false;
  const seconds = Number(relative[1]) * ({ 秒: 1, 分钟: 60, 小时: 3600 })[relative[2]];
  return seconds <= nowSeconds;
}

function readView(b) {
  const normalize = (text) => (text || "").replace(/\s+/g, " ").trim();
  const visible = (el) => {
    const style = getComputedStyle(el);
    return el.getClientRects().length > 0 && style.display !== "none" && style.visibility !== "hidden";
  };
  const nodes = (selector) => selector ? [...document.querySelectorAll(selector)].filter(visible) : [];
  const probe = (selector) => {
    const found = nodes(selector);
    const el = found.length === 1 ? found[0] : null;
    return {
      count: found.length,
      text: el ? normalize(el.textContent) : "",
      disabled: !!el && (el.disabled === true || el.hasAttribute("disabled") ||
        el.getAttribute("aria-disabled") === "true" || getComputedStyle(el).pointerEvents === "none"),
    };
  };
  const body = document.body?.innerText || "";
  const dialogs = nodes('[role="dialog"], .ant-modal').map((el) => normalize(el.textContent)).join(" ");
  return {
    url: location.href,
    login: nodes('input[placeholder="手机号"], input[placeholder="短信验证码"]').length > 0,
    challenge: /安全验证|访问异常|请完成验证|滑动验证/.test(body),
    limited: /操作过于频繁|刷新次数已用完|明天再来刷新|今日已刷新/.test(body),
    paid: /购买金卡|立即开通|去开通|支付/.test(dialogs),
    identity: probe(b.identity_selector),
    refresh: probe(b.refresh_selector),
    status: probe(b.status_selector),
    success: probe(b.success_selector),
    successSurface: probe(b.success_surface_selector),
    blocked: probe(b.blocked_selector),
  };
}

function preflight(view) {
  const url = new URL(view.url);
  if (view.login || url.hostname === "www.liepin.com") return "needs_login";
  if (url.protocol !== "https:" || url.hostname !== "c.liepin.com") return "binding_changed";
  if (view.challenge) return "challenge";
  if (view.identity.count !== 1) return "binding_changed";
  if (hash(view.identity.text) !== binding.identity_sha256) return "identity_mismatch";
  if (view.paid) return "paid_required";
  if (view.status.count === 1 && fresh(view.status.text)) return "already_refreshed";
  if (view.limited || view.blocked.count === 1) return "rate_limited";
  if (view.refresh.count !== 1 || view.refresh.text !== binding.refresh_text || view.refresh.disabled) {
    return "binding_changed";
  }
  if (binding.status_selector && view.status.count !== 1) return "binding_changed";
  if (view.success.count > 1) return "binding_changed";
  if (view.successSurface.count > 1) return "binding_changed";
  return "ready";
}

async function nativeResponse(page, events, suffix) {
  for (let round = 0; round < 12; round++) {
    const candidates = events.filter((event) => event.method === "Network.responseReceived" &&
      event.params.response.url.endsWith(suffix));
    if (candidates.length) {
      try {
        const response = await page.cdp("Network.getResponseBody", { requestId: candidates.at(-1).params.requestId });
        const body = response.base64Encoded ? Buffer.from(response.body, "base64").toString("utf8") : response.body;
        return JSON.parse(body);
      } catch (error) {
        if (/CONTROL|INACTIVE|UNASSIGNED/.test(String(error))) throw error;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 150));
    events.push(...await page.events());
  }
  return null;
}

try {
  task = await taskSpace(input.browser === "cdp" ? `猎聘每日刷新 ${nowISO}` : input.spaceId);
  const page = task.page(input.pageLabel || "p1");
  await page.cdp("Network.enable");
  await page.goto(binding.resume_url);
  try {
    await page.waitForFunction((b) => document.querySelector(b.refresh_selector) ||
      document.querySelector('input[placeholder="手机号"]'), binding, { timeout: 12000 });
  } catch (error) { if (!/timeout|timed out/i.test(String(error))) throw error; }
  for (const selector of binding.dismiss_selectors || []) {
    const canDismiss = await page.evaluate((s) => {
      const matches = [...document.querySelectorAll(s)].filter((el) => el.getClientRects().length > 0);
      return matches.length === 1;
    }, selector);
    if (canDismiss) {
      await page.click(`loc=css:${selector}`, { label: "关闭已核验推广弹窗" });
      await page.waitForSelector(selector, { state: "hidden", timeout: 5000 });
    }
  }
  const ownerResponse = await nativeResponse(page, await page.events(), "/api/com.liepin.usercx.pc.user.base-property");
  const resumeOK = !!ownerResponse?.data?.resId && hash(ownerResponse.data.resId) === binding.resume_id_sha256;
  const before = await page.evaluate(readView, binding);
  const initialCheck = preflight(before);
  const checked = ["ready", "already_refreshed"].includes(initialCheck) && !resumeOK ? "identity_mismatch" : initialCheck;
  result = { status: checked, attempted: false, verified: checked === "already_refreshed" };
  if (checked === "ready" && !dryRun) {
    // Record before dispatch: a lost browser response must not cause a second click.
    await fs.writeFile(markerPath, JSON.stringify({ day, at: nowISO }) + "\n", { mode: 0o600 });
    attempted = true;
    await page.click(`loc=css:${binding.refresh_selector}`, { label: "刷新本人猎聘简历" });
    try {
      await page.waitForFunction(({ b, previousStatus, previousSuccess, previousSurface }) => {
        const text = (selector) => {
          if (!selector) return "";
          const matches = [...document.querySelectorAll(selector)].filter((el) =>
            el.getClientRects().length && getComputedStyle(el).visibility !== "hidden");
          return matches.length === 1 ? (matches[0].textContent || "").replace(/\s+/g, " ").trim() : "";
        };
        const surface = b.success_surface_selector && [...document.querySelectorAll(b.success_surface_selector)].some(el => el.getClientRects().length > 0);
        return text(b.status_selector) !== previousStatus || text(b.success_selector) !== previousSuccess || (surface && !previousSurface) ||
          /操作过于频繁|请完成验证|刷新次数已用完/.test(document.body?.innerText || "");
      }, { b: binding, previousStatus: before.status.text, previousSuccess: before.success.text, previousSurface: before.successSurface.count > 0 }, { timeout: 8000 });
    } catch (error) {
      // A normal wait timeout still permits a final observation, never another click.
      if (!/timeout|timed out/i.test(String(error))) throw error;
    }
    const after = await page.evaluate(readView, binding);
    const native = await nativeResponse(page, await page.events(), "/api/com.liepin.cresume.refresh-resume");
    const afterCheck = preflight(after);
    const newSuccess = after.success.count === 1 && after.success.text === binding.success_text &&
      before.success.text !== after.success.text;
    const changedTime = after.status.count === 1 && after.status.text !== before.status.text && fresh(after.status.text);
    const newSurface = after.successSurface.count === 1 && before.successSurface.count === 0;
    const nativeSuccess = Number(native?.flag) === 1;
    const nativeFailure = native && Number(native.flag) !== 1;
    const identityOK = after.identity.count === 1 && hash(after.identity.text) === binding.identity_sha256;
    const samePage = new URL(after.url).hostname === "c.liepin.com";
    if (identityOK && resumeOK && samePage && !after.challenge && !after.paid && !nativeFailure && (nativeSuccess || newSuccess || changedTime || newSurface)) {
      result = { status: "success", attempted: true, verified: true, evidence: nativeSuccess ? "native_api_flag_1" : (newSuccess ? "new_success_notice" : (newSurface ? "verified_success_surface" : "changed_refresh_time")) };
    } else {
      const definite = ["needs_login", "identity_mismatch", "paid_required", "rate_limited", "challenge"];
      result = { status: definite.includes(afterCheck) ? afterCheck : "unverified", attempted: true, verified: false };
    }
  }
} catch (error) {
  const message = String(error);
  controlled = /CONTROL|INACTIVE|UNASSIGNED|USER_OWNED|NAME_IN_USE/.test(message);
  result = { status: controlled ? "user_control" : (attempted ? "unverified" : "browser_error"), attempted, verified: false, error_kind: error?.name || "Error" };
} finally {
  if (task && !controlled && input.browser === "cdp") {
    try { await task.finish({ keep: [] }); }
    catch { result = { ...result, cleanup_pending: true }; }
  }
}
console.log("LIEPIN_RESULT " + JSON.stringify(result));
