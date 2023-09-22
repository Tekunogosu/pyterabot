#!/usr/bin/env python3
import random

from sqlalchemy import create_engine, text, MetaData, Table, Column, Integer, \
    String, ForeignKey, insert, select, bindparam
from sqlalchemy.orm import Session, DeclarativeBase

from utils import vv, now

engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)
# engine = create_engine("sqlite+pysqlite:///:memory:", echo=True)

metadata_obj = MetaData()


with engine.connect() as conn:
    conn.execute(text("CREATE TABLE some_table (x int, y int)"))
    conn.execute(
        text("INSERT INTO some_table (x, y) VALUES (:x, :y)"),
        [{"x": random.randint(1, 99), "y": random.randint(1, 99)} for _ in range(15)]
    )
    conn.commit()

with engine.begin() as conn:
    conn.execute(
        text("INSERT INTO some_table (x, y) VALUES (:x, :y)"),
        [{"x": 93, "y": 11}],
    )

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM some_table"))
    for row in result:
        print(f"x: {row.x} y: {row.y}")

with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM some_table WHERE x >= :x"), {"x": 15})

    print(f"total: {len(result.keys())}")

    for r in result:
        print(f"{r.x, r.y}")

stmt = text("SELECT * FROM some_table WHERE y > :y ORDER BY x, y")
with Session(engine) as session:
    result = session.execute(stmt, {"y": 6})
    for r in result:
        print(f"x: {r.x} y:{r.y}")


with Session(engine) as session:
    result = session.execute(
        text("UPDATE some_table SET y=:y WHERE x=:x"),
        [{"x": 9, "y": 11}, {"x": 13, "y": 15}],
    )
    session.commit()

user_table = Table(
    "user_account",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    Column("name", String(30)),
    Column("fullname", String),
)

address_table = Table(
    "address",
    metadata_obj,
    Column("id", Integer, primary_key=True),
    # Datatype for column is inferred by the ForeignKey constraint
    Column("user_id", ForeignKey("user_account.id")),
    Column("email_address", String, nullable=False),
)

metadata_obj.create_all(engine)


stmt = insert(user_table).values(name="violet", fullname="violet sexypants")
print(stmt)
cp = stmt.compile(engine)


with engine.connect() as conn:
    res = conn.execute(insert(user_table), [
        {"name": "tera", "fullname": "Tera Hollows"},
        {"name": "violet", "fullname": "violet eldridge"},
    ])
    conn.commit()


scaral_subq = (
    select(user_table.c.id)
    .where(user_table.c.name == bindparam("username"))
    .scalar_subquery()
)

with engine.connect() as conn:
    res = conn.execute(
        insert(address_table).values(user_id=scaral_subq),
        [
            {"username": "tacos", "email_address": "tacos@tacos.tacos"},
            {"username": "something", "email_address": "else@none.com"}
        ],
    )
    conn.commit()




