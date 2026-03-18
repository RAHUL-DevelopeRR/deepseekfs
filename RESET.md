# Reset Index

If you want to force a full re-scan, delete the storage folder:

```bash
# Windows
rmdir /s /q storage

# Mac / Linux
rm -rf storage/
```

Then restart:
```bash
python run.py
```
