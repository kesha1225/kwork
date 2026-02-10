from kwork.schema import Category, DialogMessage, ParentCategory, SubCategory
from kwork.schema.kwork_object import KworkObject


def test_dialog_message_aliases_and_nested_last_message() -> None:
    obj = DialogMessage(
        user_id=123,
        username="u",
        lastOnlineTime=1700000000,
        allowedDialog=True,
        lastMessage={
            "fromUsername": "bob",
            "fromUserId": 5,
            "profilePicture": "pic.png",
            "message": "hi",
        },
        extraField="ignored",
    )

    assert obj.user_id == 123
    assert obj.last_online_time == 1700000000
    assert obj.allowed_dialog is True
    assert obj.last_message_obj is not None
    assert obj.last_message_obj.from_username == "bob"
    assert obj.last_message_obj.from_user_id == 5
    assert obj.last_message_obj.profile_picture == "pic.png"
    assert obj.last_message_obj.message == "hi"

    dumped = obj.model_dump(by_alias=True)
    assert "lastOnlineTime" in dumped
    assert "allowedDialog" in dumped
    assert "lastMessage" in dumped


def test_category_inheritance_parses_nested_tree() -> None:
    data = {
        "id": 1,
        "name": "Root",
        "subcategories": [
            {
                "id": 2,
                "name": "Sub",
                "subcategories": [
                    {"id": 3, "name": "Leaf"},
                ],
            }
        ],
    }

    root = ParentCategory(**data)
    assert root.subcategories is not None
    assert isinstance(root.subcategories[0], SubCategory)
    assert root.subcategories[0].subcategories is not None
    assert isinstance(root.subcategories[0].subcategories[0], Category)
    assert root.subcategories[0].subcategories[0].name == "Leaf"


def test_kwork_object_parses_nested_models() -> None:
    obj = KworkObject(
        id=1,
        cover={"phone": "p.png", "tablet": "t.png"},
        worker={
            "id": 9,
            "username": "w",
            "rating": 4.9,
        },
        activity={"views": 10, "orders": 2},
        isSubscription=True,
    )

    assert obj.cover is not None
    assert obj.cover.phone == "p.png"
    assert obj.worker is not None
    assert obj.worker.username == "w"
    assert obj.activity is not None
    assert obj.activity.views == 10
    assert obj.is_subscription is True
