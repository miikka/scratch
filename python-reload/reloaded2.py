print(f"executing {__name__=}")

try:
    a
except:
    a = 0

a += 1

def fun():
    print(f"{a=}")