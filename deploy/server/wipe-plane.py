# Wipe v2: delete the resurrected old workspaces, print counts, and let the
# caller watch from psql whether they come back.
from django.db import transaction
from plane.db.models import Workspace, User, Issue, Project, FileAsset

KEEP_WS = {"1"}

with transaction.atomic():
    total = Workspace.objects.count()
    gone_ws = Workspace.objects.exclude(slug__in=KEEP_WS).delete()
    Issue.objects.all().delete()
    Project.objects.all().delete()
    FileAsset.objects.filter(is_uploaded=False).delete()

print("before:", total)
print("deleted:", gone_ws[0])
print("workspaces now:", list(Workspace.objects.values_list("slug", flat=True)))
print("issues now:", Issue.objects.count())
print("projects now:", Project.objects.count())
print("users now:", sorted(User.objects.values_list("email", flat=True)))
