import sys
import os

print(f"TEST CONTENT, arg={sys.argv[1]}")

print(__file__)

print(os.getcwd())

# Test persistence of file
f = open("/app/test.txt", "w")
f.write(f"TEST CONTENT, arg={sys.argv[1]}")
f.close()
