import pytest

from oso import Oso, polar_class, Roles
from polar import exceptions


class User:
    name: str = ""

    def __init__(self, name=""):
        self.name = name

class Organization:
    id: str = ""

    def __init__(self, id):
        self.id = id

class Repository:
    id: str = ""
    public: bool
    org: Organization

    def __init__(self, id, org, public=False):
        self.id = id
        self.public = public
        self.org = org

class Issue:
    id: str = ""
    public: bool
    repo: Repository

    def __init__(self, id, repo, public=False):
        self.id = id
        self.public = public
        self.repo = repo

@pytest.fixture
def test_roles():
    oso = Oso()
    oso.register_class(User)
    oso.register_class(Repository)
    oso.register_class(Organization)

    ## ROLE DEFINITION

    # does the user need to be a Python class?
    # probably want to support dicts and strings/ints for users and resources
    # if we do that need to figure out how to make the "id" fields default to the object itself
    # oso.create_roles(
    #     user=Actor,
    #     user_id="name",
    #     roles=["ADMIN", "USER"],
    #     # exclusive=True,
    #     # inherits=[("Admin", "User")],
    # )
    # oso.create_roles(user=Actor, resource=Widget, resource_id="id", roles=["OWNER"])
    # role constraints?



    # REPOSITORY PERMISSION
    # permission: (action, resource)
    # where top-level resource is always a tenant

    # Repo permission definitions
    oso.create_permission_set(resource_type=Repository, actions=["read", "write", "list_issues"])

    # Issue permissions
    oso.create_permission_set(resource_type=Issue, actions=["read", "write"])

    # Issue relationship
    oso.add_parent_relationship(name="issue_repo", child=Issue, parent=Repository, get=lambda child: child.repo)

    # Repo roles
    ## role definition
    oso.create_role(resource_type=Repository, name="READ")
    oso.create_role(resource_type=Repository, name="WRITE")

    ## permission assignment
    oso.add_role_permission(resource_type=Repository, name="READ", permission={"action": "read", "resource": Repository})
    oso.add_role_permission(resource_type=Repository, name="READ", permission={"action": "list_issues", "resource": Repository})
    oso.add_role_permission(resource_type=Repository, name="READ", permission={"action": "read", "resource": Issue}, relationship="issue_repo")

    oso.add_role_permission(resource_type=Repository, name="WRITE", permission={"action": "write", "resource": Repository})

    ## role inheritance
    oso.role_implies(role={"role": "WRITE", "resource_type": Repository}, implies={"role": "READ", "resource_type": Repository})

    # Organization permission definitions
    oso.create_permission_set(resource_type=Organization, actions=["read", "create_repo", "list_roles", "list_repos"])

    ## role definition
    oso.create_role(resource_type=Organization, name="OWNER")
    oso.create_role(resource_type=Organization, name="MEMBER")

    ## permission assignment
    oso.add_role_permission(resource_type=Organization, name="MEMBER", permission={"action": "read", "resource": Organization})
    oso.add_role_permission(resource_type=Organization, name="MEMBER", permission={"action": "list_repos", "resource": Organization})
    oso.add_role_permission(resource_type=Organization, name="MEMBER", permission={"action": "create_repo", "resource": Organization})

    oso.add_role_permission(resource_type=Organization, name="OWNER", permission={"action": "list_roles", "resource": Organization})

    ## implied roles within a single resource type
    oso.role_implies(role={"role": "OWNER", "resource_type": Organization}, implies={"role": "MEMBER", "resource_type": Organization})


    # Resource relationships

    # This still only works in Python (not super clear how to abstract across API)
    oso.add_parent_relationship(name="repo_org", child=Repository, parent=Organization, get=lambda child: child.org)

    # implied roles across resource types
    ## if you are an org owner, you are an admin in every repo of the org
    ## need a relationship if the resource types don't match
    oso.role_implies(role={"role": "OWNER", "resource_type": Organization}, implies={"role": "ADMIN", "resource_type": Repository}, relationship="repo_org")


    # Evaluating permissions

    polar="""
    allow(user, action, resource) if
        Roles.role_allows(user, action, resource);

    allow(user, action, repo: Repository) if
        repo.public and
        Roles.role_allows(user, action, resource) and cut;

    """


    # NOTES
    ########
    # problems with above
    # - hard to understand the relationships between everything because it's flat
    # - very redundant
    # - easy to make a typo/mistake because everything is a string

    # open questions
    # - how do we handle public/private? For simple stuff like that it would be really useful to add conditions on role-permission assignments
    #       - could also use deny logic in the policy or check role permissions in the policy so you can add a condition
    # - role constraints? mutually exclusive? How do we deal with this?
    #       - roles that are hierarchical are probably also mutually exclusive
    #       - use cases that only have global roles might not want mutually exclusive roles









    # TODO:
    # -[x] define API for creating roles
    # -[x] define API for creating, adding/removing permissions to roles
    # -[x] define API for defing resource relationships
    # -[] think through UX for devs and what features this supports in the frontend
    # -[] how do dynamic permissions get evaluated with `is_allowed?`

    ### BRAINSTORMING

    # {user: the_actor, role: "ADMIN", resource: the_widget, kind: "Widget"}

    role_config = """
    GlobalRole = {
        user: Actor,
        user_id: "name"
        roles: ["ADMIN", "USER"]
    }

    WidgetRole = {
        user: Actor,
        user_id: "name",
        resource: Widget,
        resource_id: "id"
        roles: ["OWNER"]
    }


    scope resource: Widget {
        allow(user, action, resource) if
            has_role(user, "ADMIN", resource) and


        allow_role("ADMIN", _action, resource: Widget);
        allow_role("MEMBER", action, resource: Widget) if
            action in ["read", "write"];

        allow(user: Actor, action, resource: Widget) if
            allow_role()

    }
    """

    rules = """
    # permissions on roles
    allow(user: Actor, action, widget: Widget) if
        role = Roles.get_user_roles(user) and
        role.has_perm(action, widget) and
        not widget.private;

    # could also just evaluate role permissions in the library, with no hook from Polar, and introduce deny logic to Polar



    allow(user: Actor, "UPDATE", widget: Widget) if
        {role: "ADMIN"} in Roles.get_user_roles(user) or
        {role: "OWNER"} in Roles.get_user_roles(user, widget) or
        widget.public;

    role_allow(role: {role: "OWNER", resource: resource}, _action, resource: Widget);

    role_allow(role: WidgetRole, _action, resource: Widget) if
        role.widget = resource;

    role_allow(role: {role: "OWNER", resource: resource.parent}, _action, resource: Widget);


    #allow(user: Actor, "UPDATE", widget: Widget) if
    #    Roles.user_in_role(user, {role: "ADMIN"}) or
    #    Roles.user_in_role(user, "OWNER", widget) or
    #   widget.public;

    allow(user: Actor, "UPDATE", resource: Widget) if
        {role: "OWNER"} in Roles.user_roles(user, resource.parent);

    #allow(user: Actor, "UPDATE", resource: Widget) if
    #    Roles.user_in_role(user, role, resource.parent) and
    #    role_allow(role, action, resource);

    allow(user: Actor, action, resource: Widget) if
        allow(user, action, resource.parent);

    allow(user: Actor, _action, resource: WidgetParent) if
        Roles.user_in_role(user, "ADMIN", resource);
    """

    # need to know
    # User / Actor class
    # Resources the user can have roles on.
    #

    roles = Roles()


## Static vs dynamic

### STATIC (Polar?)
#### What Role types exist
#### Role inheritance
#### What permissions exist
#### Custom logic

### DYNAMIC (DB)
#### Role instances
#### User-role assignments
#### Role-permission assignments
#### Role-resource relationships

## What changes a lot?
# custom role creation
# user-role-resource

## What doesn't change a lot?
# role-permission
# Role levels
# role scopes/types
# permissions that exist