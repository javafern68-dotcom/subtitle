"""PyInstaller hook for the Avro Bengali transliteration package.

The upstream PyInstaller hook named ``hook-avro`` targets the unrelated Apache
Avro serialization package.  This project uses ``avro.py`` (Bengali phonetic
transliteration), so its normal package data is collected by the build command
and the Apache-specific schema files must not be requested.
"""

datas: list[tuple[str, str]] = []
hiddenimports: list[str] = []
