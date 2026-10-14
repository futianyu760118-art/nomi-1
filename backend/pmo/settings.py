import base64
import hashlib
import os
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from .models import SystemSetting

SECRET_FIELDS = ("planeToken", "gitToken", "llmKey")
ENV = {"planeUrl": "PLANE_URL", "planeToken": "PLANE_API_TOKEN", "workspace": "PLANE_WORKSPACE",
       "planeProject": "PLANE_PROJECT", "gitUrl": "GIT_URL", "gitToken": "GIT_TOKEN",
       "repository": "GIT_REPOSITORY", "llmUrl": "LLM_BASE_URL", "llmKey": "LLM_API_KEY", "model": "LLM_MODEL"}
DEFAULTS = dict(planeUrl="", planeToken="", workspace="", planeProject="", gitProvider="gitlab",
                gitUrl="", gitToken="", repository="", llmUrl="", llmKey="", model="",
                temperature=0.1, maxTokens=3000, autoSync=False, syncInterval=300,
                maxAiFiles=20, maxAiDiffSize=50000, maxAiCodeSize=120000,
                weightP0=5, weightP1=3, weightP2=1)


def cipher(secret):
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def read_settings(db, secret, public=False):
    row = db.get(SystemSetting, "integrations")
    result = {**DEFAULTS, **(row.data if row else {})}
    crypt = cipher(secret)
    for key in SECRET_FIELDS:
        value = result[key]
        result[key] = crypt.decrypt(value.encode()).decode() if value else ""
    for key, env in ENV.items():
        if not result[key]:
            result[key] = os.getenv(env, "")
    for key, env in (("maxAiFiles", "MAX_AI_FILES"), ("maxAiDiffSize", "MAX_AI_DIFF_SIZE"), ("maxAiCodeSize", "MAX_AI_CODE_SIZE")):
        if not row and os.getenv(env):
            result[key] = int(os.getenv(env))
    if public:
        for key in SECRET_FIELDS:
            result[key + "Configured"] = bool(result.pop(key))
    return result


def save_settings(db, secret, changes):
    if not isinstance(changes, dict) or set(changes) - set(DEFAULTS):
        raise ValueError("包含未知配置项")
    result = read_settings(db, secret)
    # Omitted secrets are preserved; an explicit empty string clears the saved value.
    result.update(changes)
    for key in ("planeUrl", "gitUrl", "llmUrl"):
        if result[key]:
            parsed = urlsplit(result[key])
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("服务地址必须为不含凭据、查询参数的 HTTP(S) URL")
    if result["gitProvider"] != "gitlab":
        raise ValueError("本版已实现 GitLab；GitHub / Gitea 保留适配接口")
    for key, low, high in (("syncInterval", 60, 86400), ("maxTokens", 256, 16000), ("maxAiFiles", 1, 50),
                          ("maxAiDiffSize", 1000, 200000), ("maxAiCodeSize", 1000, 500000),
                          ("weightP0", 1, 20), ("weightP1", 1, 20), ("weightP2", 1, 20)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError("{} 必须是 {} 到 {} 的整数".format(key, low, high))
    if type(result["autoSync"]) is not bool:
        raise ValueError("autoSync 必须是布尔值")
    if not isinstance(result["temperature"], (int, float)) or not 0 <= result["temperature"] <= 2:
        raise ValueError("Temperature 必须在 0 到 2 之间")
    for key, value in result.items():
        if key not in ("autoSync", "temperature") and key not in ("syncInterval", "maxTokens", "maxAiFiles", "maxAiDiffSize", "maxAiCodeSize", "weightP0", "weightP1", "weightP2"):
            if not isinstance(value, str) or len(value) > 2000:
                raise ValueError("无效配置字段: " + key)
    crypt = cipher(secret)
    stored = dict(result)
    for key in SECRET_FIELDS:
        stored[key] = crypt.encrypt(result[key].encode()).decode() if result[key] else ""
    row = db.get(SystemSetting, "integrations")
    if row:
        row.data = stored
    else:
        db.add(SystemSetting(key="integrations", data=stored))
    db.commit()
    return read_settings(db, secret, public=True)
