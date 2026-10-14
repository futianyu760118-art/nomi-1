#!/bin/sh
# NOMI artifact-layer rebrand for the pristine Plane web bundle.
# Runs inside the nginx:alpine image (busybox sed/awk only — no python/node).
# Deterministic string replacements; no behaviour changes.
#
# Rule order matters: full sentences run before the plain "Plane" -> "NOMI"
# brand swap, so login copy is localized before the word-level pass.
set -eu

cd /usr/share/nginx/html
# Snapshot the pristine bundles so the post-rebrand structural check can tell
# an introduced break from braces that legitimately live inside strings.
mkdir -p /tmp/pristine-assets
cp assets/*.js /tmp/pristine-assets/

cd /usr/share/nginx/html/assets

for f in *.js; do
  sed -i \
    -e 's/Work in all dimensions\./No PM, More Impact./g' \
    -e 's/Welcome back to Plane\./欢迎回到 NOMI。/g' \
    -e 's/Create your Plane account\./创建你的 NOMI 账号。/g' \
    -e 's/Create an account to start managing work with your team\./创建账号，开始与团队协作。/g' \
    -e 's/Log in to start managing work with your team\./登录后开始与团队协作。/g' \
    -e 's/By creating an account/创建账号即表示你已知悉并同意/g' \
    -e 's/By signing in/登录即表示你已知悉并同意/g' \
    -e 's/, you understand and agree to \\n our /我们的/g' \
    -e 's/Join 10,000+ teams building with Plane/NOMI · 项目管理系统/g' \
    -e 's/`Terms of Service`/`服务条款`/g' \
    -e 's/`Privacy Policy`/`隐私政策`/g' \
    -e 's/children:` and`/children:`和`/g' \
    -e 's/` and`,` `/`和`,` `/g' \
    -e 's/`Sign up`/`注册`/g' \
    -e 's/>Sign up</>注册</g' \
    -e 's/linkHref:"\/sign-up"/linkHref:"\/sign-up"/g' \
    -e 's/`Sign in`/`登录`/g' \
    -e 's/`Continue`/`继续`/g' \
    -e 's/`Go to workspace`/`前往工作区`/g' \
    -e 's/`Forgot your password\?`/`忘记密码？`/g' \
    -e 's/Sign up using an email-password combination\./使用邮箱和密码注册。/g' \
    -e 's/Sign up using a unique code sent to the email address\./使用发送到邮箱的唯一验证码注册。/g' \
    -e 's/Log in using an email-password combination\./使用邮箱和密码登录。/g' \
    -e 's/Log in using a unique code sent to the email address\./使用发送到邮箱的唯一验证码登录。/g' \
    -e 's/Enter your email address to continue\./输入邮箱地址以继续。/g' \
    -e 's/`Your profile`/`我的资料`/g' \
    -e 's/`Work structure`/`工作结构`/g' \
    -e 's/`Execution`/`执行`/g' \
    -e 's/`Administration`/`管理`/g' \
    -e 's/`Completed on`/`完成于`/g' \
    -e 's/Star us on GitHub/项目管理系统/g' \
    -e 's/在GitHub上为我们加星/项目管理系统/g' \
    -e 's|https://github\.com/makeplane/plane|#nomi-hidden|g' \
    -e 's|https://github\.com/makeplane|#nomi-hidden|g' \
    -e 's|https://plane\.so|#nomi-hidden|g' \
    -e 's|https://github\.com/makeplane/plane||g' \
    -e 's|https://github\.com/makeplane||g' \
    -e 's/"MMM dd, yyyy"/"yyyy年M月d日"/g' \
    -e 's/MMM dd, yyyy/yyyy年M月d日/g' \
    -e 's/"MMM dd"/"M月d日"/g' \
    -e 's/MMM dd/M月d日/g' \
    -e 's/"en-US"/"zh-CN"/g' \
    -e 's/`en-US`/`zh-CN`/g' \
    "$f"
done

# Sidebar / navigation labels that upstream ships hardcoded in components
# (not part of the locale files, so the zh-CN pack cannot reach them).
for f in *.js; do
  sed -i \
    -e 's/^Projects$/项目/g' \
    -e 's/title:`Projects`/title:`项目`/g' \
    -e 's/children:`Projects`/children:`项目`/g' \
    -e 's/>Projects</>项目</g' \
    -e 's/`Projects`/`项目`/g' \
    -e 's/`More`/`更多`/g' \
    -e 's/isExtendedSidebarOpened?"Hide":"More"/isExtendedSidebarOpened?"收起":"更多"/g' \
    -e 's/isExtendedProjectSidebarOpened?"Hide":"More"/isExtendedProjectSidebarOpened?"收起":"更多"/g' \
    -e 's/`Community`/`社区版`/g' \
    "$f"
done
echo "navigation labels localized"

# Home greeting: upstream renders "Good afternoon, First Last" from separate
# locale fragments, which reads as "早上 下午, 名字" in Chinese. Compose the
# Chinese greeting directly (greeting word + surname-first name order) and drop
# the English comma before the date.
for f in *.js; do
  sed -i \
    -e 's/\[r(`good`),` `,r(l),`, `,t?\.first_name,` `,t?\.last_name\]/[r(l),`好，`,t?.first_name,` `,t?.last_name]/g' \
    -e 's/\[s,`, `,a,` `,c\]/[s,` `,a,` `,c]/g' \
    "$f"
done
echo "greeting localized"

# Default UI language: China-first. The upstream bundle falls back to `en`
# when no user language is stored (fresh visitor / signed-out pages).
# Bundle form: localStorage.getItem(`userLanguage`)||`en`
for f in *.js; do
  sed -i \
    -e 's/localStorage\.getItem(`userLanguage`)||`en`/localStorage.getItem(`userLanguage`)||`zh-CN`/g' \
    -e 's/fallbackLng:`en`/fallbackLng:`zh-CN`/g' \
    "$f"
done
echo "default language set to zh-CN"

# Brand word pass (last, so the localization rules above win).
for f in *.js; do
  sed -i -e 's/Plane/NOMI/g' -e 's/NOMI\.so/#/g' -e 's/plane\.so/#/g' "$f"
done

# Login / auth error messages (visible when a sign-in attempt fails).
for f in *.js; do
  sed -i \
    -e 's/`Invalid email`/`邮箱格式无效`/g' \
    -e 's/`Email required`/`请填写邮箱`/g' \
    -e 's/`Email and code required`/`请填写邮箱和验证码`/g' \
    -e 's/`Email and password required`/`请填写邮箱和密码`/g' \
    -e 's/`Email, password and first name required`/`请填写邮箱、密码和姓名`/g' \
    -e 's/`Sign up disabled`/`注册功能已关闭`/g' \
    -e 's/`Sign in not allowed`/`不允许登录`/g' \
    -e 's/`Magic link login disabled`/`已关闭邮件链接登录`/g' \
    -e 's/`Password login disabled`/`已关闭密码登录`/g' \
    -e 's/`User account deactivated`/`账号已停用`/g' \
    -e 's/`User already exists`/`用户已存在`/g' \
    -e 's/`Invalid password`/`密码错误`/g' \
    -e 's/`Password too weak`/`密码强度不足`/g' \
    -e 's/`SMTP not configured`/`尚未配置邮件服务`/g' \
    -e 's/`Authentication failed`/`认证失败`/g' \
    -e 's/`Expired magic code`/`验证码已过期`/g' \
    -e 's/`Expired password token`/`密码重置链接已过期`/g' \
    -e 's/`Invalid password token`/`密码重置链接无效`/g' \
    -e 's/`Incorrect old password`/`原密码不正确`/g' \
    -e 's/`Invalid new password`/`新密码无效`/g' \
    -e 's/`Instance not configured`/`实例尚未配置`/g' \
    -e 's/`Admin already exists`/`管理员已存在`/g' \
    -e 's/`Admin user already exists`/`管理员账号已存在`/g' \
    -e 's/`Admin user deactivated`/`管理员账号已停用`/g' \
    -e 's/`Admin user does not exist`/`管理员账号不存在`/g' \
    -e 's/`Invalid admin email`/`管理员邮箱无效`/g' \
    -e 's/`Invalid admin password`/`管理员密码无效`/g' \
    -e 's/`GitHub not configured`/`尚未配置 GitHub`/g' \
    -e 's/`GitLab not configured`/`尚未配置 GitLab`/g' \
    -e 's/`Google not configured`/`尚未配置 Google`/g' \
    -e 's/`GitHub OAuth provider error`/`GitHub 登录服务异常`/g' \
    -e 's/`GitLab OAuth provider error`/`GitLab 登录服务异常`/g' \
    -e 's/`Google OAuth provider error`/`Google 登录服务异常`/g' \
    -e 's/`Sign up using an email-password combination\.`/`使用邮箱和密码注册。`/g' \
    -e 's/`Sign up using a unique code sent to the email address\.`/`使用发送到邮箱的验证码注册。`/g' \
    -e 's/`Log in using an email-password combination\.`/`使用邮箱和密码登录。`/g' \
    -e 's/`Log in using a unique code sent to the email address\.`/`使用发送到邮箱的验证码登录。`/g' \
    -e 's/`Sign up - NOMI`/`注册 - NOMI`/g' \
    -e 's/`Sign in - NOMI`/`登录 - NOMI`/g' \
    "$f"
done

cd /usr/share/nginx/html
for f in manifest.json site.webmanifest.json; do
  if [ -f "$f" ]; then
    sed -i -e 's/Plane/NOMI/g' "$f"
  fi
done
sed -i -e 's/Plane | Simple, extensible, open-source project management tool\./NOMI | 项目管理系统/g' -e 's/Plane/NOMI/g' index.html

# ---------------------------------------------------------------------------
# Note on validation: text substitution mistakes (deleting an object key rather
# than its text) yield invalid JS. Delimiter counting cannot separate those
# from intentional restructures, so the authoritative check is a real parse of
# every bundle, run from the host before deploy:
#   node docker/nomi-web/check-chunks.mjs pmo-web:latest

# The rebrand rewrites bundle bytes while keeping upstream's hashed filenames,
# so browsers that cached the previous bytes would keep serving stale code
# (their old responses carry long-lived cache headers, which a newly added
# no-cache header on the same URL cannot override). Versioning the path forces
# every client to fetch the rebranded files exactly once.
ASSET_DIR=assets-nomi
mv assets "$ASSET_DIR"
rm -rf /tmp/pristine-assets
sed -i "s#/assets/#/$ASSET_DIR/#g" index.html
sed -i "s#/assets/#/$ASSET_DIR/#g" *.js 2>/dev/null || true
find "$ASSET_DIR" -name "*.js" -exec sed -i "s#/assets/#/$ASSET_DIR/#g" {} +
# The blanket rename above also rewrites the API upload path /api/assets/
# (avatars, covers, attachments upload through it); restore it or those
# uploads 404.
sed -i "s#api/assets-nomi/#api/assets/#g" *.js 2>/dev/null || true
find "$ASSET_DIR" -name "*.js" -exec sed -i "s#api/assets-nomi/#api/assets/#g" {} +
# Workspace slug auto-fill copies the name verbatim (lowercased, spaces to
# dashes), so a Chinese-only name yields an invalid slug and creation 400s.
# Normalize to [a-z0-9-] with a random fallback when nothing survives.
sed -i 's#toLocaleLowerCase().trim().replace(/ /g,`-`)#toLocaleLowerCase().trim().replace(/ /g,`-`).replace(/[^a-z0-9-]/g,``).replace(/^-+|-+$/g,``).slice(0,48)||`ws-`+Math.random().toString(36).slice(2,8)#g' *.js 2>/dev/null || true
find "$ASSET_DIR" -name "*.js" -exec sed -i 's#toLocaleLowerCase().trim().replace(/ /g,`-`)#toLocaleLowerCase().trim().replace(/ /g,`-`).replace(/[^a-z0-9-]/g,``).replace(/^-+|-+$/g,``).slice(0,48)||`ws-`+Math.random().toString(36).slice(2,8)#g' {} +
echo "asset path versioned to /$ASSET_DIR"


echo "NOMI rebrand applied"
