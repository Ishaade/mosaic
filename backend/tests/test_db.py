from app.db import crud


def test_create_user_and_get(db):
    user = crud.create_user(db, name="Ada")
    assert user.id is not None
    assert crud.get_user(db, user.id).name == "Ada"


def test_conversation_and_messages(db):
    user = crud.create_user(db)
    conv = crud.create_conversation(db, user_id=user.id, persona="tutor")
    crud.add_message(db, conv.id, role="user", content="What is 2+2?")
    crud.add_message(db, conv.id, role="assistant", content="4")

    messages = crud.list_messages(db, conv.id)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].content == "4"


def test_list_conversations_only_for_that_user(db):
    a = crud.create_user(db)
    b = crud.create_user(db)
    crud.create_conversation(db, user_id=a.id, persona="friend")
    crud.create_conversation(db, user_id=b.id, persona="parent")

    assert len(crud.list_conversations_for_user(db, a.id)) == 1
    assert crud.list_conversations_for_user(db, a.id)[0].persona == "friend"


def test_history_budget_keeps_newest(db):
    user = crud.create_user(db)
    conv = crud.create_conversation(db, user_id=user.id, persona="friend")
    crud.add_message(db, conv.id, role="user", content="AAAA")  # older
    crud.add_message(db, conv.id, role="assistant", content="BBBB")
    crud.add_message(db, conv.id, role="user", content="CCCC")  # newest

    # Budget that fits only the last two messages (4+4=8 chars)
    recent = crud.get_recent_messages_for_llm(db, conv.id, budget=8)
    assert [m.content for m in recent] == ["BBBB", "CCCC"]
