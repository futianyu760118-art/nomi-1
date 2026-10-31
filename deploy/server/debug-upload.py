# Which slug forms does the workspace-create API accept?
from rest_framework.test import APIClient
from plane.db.models import User, Workspace

user = User.objects.get(email="3420849544@qq.com")
c = APIClient()
c.force_authenticate(user=user)

cases = [
    {"name": "恒剑AI中台", "slug": "恒剑ai中台"},
    {"name": "恒剑AI中台", "slug": "hengjian-ai"},
    {"name": "恒剑AI中台", "slug": ""},
    {"name": "恒剑AI中台"},
]
for body in cases:
    r = c.post("/api/workspaces/", {**body, "organization_size": "2-10"}, format="json")
    print(repr(body.get("slug")), "->", r.status_code, str(r.data)[:120])
    if r.status_code == 201:
        Workspace.objects.get(id=r.data["id"]).delete()
