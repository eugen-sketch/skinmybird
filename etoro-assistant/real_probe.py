#!/usr/bin/env python3
"""Sonda cont REAL, doar citire: cate apeluri la portofoliu reusesc si cu ce cod HTTP esc (fara date de cont in log)."""
import time

from etoro import EToroDemo, EToroError, EToroHTTPError

api = EToroDemo(real=True)
for i in range(1, 6):
    try:
        v = api.credit(fresh=True)
        print(f"{i}: ok credit={'citit' if v is not None else 'lipsa'}")
    except EToroHTTPError as e:
        print(f"{i}: HTTP {e.status}: {str(e)[-160:]}")
    except EToroError as e:
        print(f"{i}: {type(e).__name__}: {str(e)[:160]}")
    time.sleep(3)
