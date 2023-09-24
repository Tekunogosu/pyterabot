#!/usr/bin/env python3
import datetime
import os


def now():
    return datetime.datetime.now()


def vv(x):
    print(vars(x))


def getenv(key:str) -> str:
    value = os.getenv(key)
    if value is None:
        raise ValueError(f"Environment must contain variable '{key}'")
    return value
