# Bangla Subtitle Studio V1

বাংলা ভিডিও থেকে স্বয়ংক্রিয় বাংলা সাবটাইটেল তৈরি, লেখা ও স্টাইল পরিবর্তন, লোগো বসানো, ভিডিওর রং ঠিক করা এবং নতুন MP4 export করার Windows desktop software।

## Windows installer তৈরি

সবচেয়ে সহজ পদ্ধতি: ZIP Extract করে `UPLOAD_AND_BUILD.bat`-এ double-click করুন। Browser-এ GitHub login অনুমোদন করার পর software files upload, Windows build এবং Setup EXE download স্বয়ংক্রিয়ভাবে হবে।

বিকল্পভাবে repository-র files `main` branch-এ upload/commit করলেও GitHub Actions Windows installer তৈরি করবে। Build শেষ হলে repository-র **Releases** অংশে `v1.0.0` release থেকে নিচের file-টি download করুন:

`Bangla_Subtitle_Studio_Setup_V1.exe`

Setup file-এ Python runtime এবং FFmpeg/FFprobe/FFplay bundled থাকে। ব্যবহারকারীকে এগুলো আলাদাভাবে install করতে হবে না। বাংলা subtitle তৈরির সময় শুধু Internet, একটি OpenAI API key এবং API balance প্রয়োজন।

সফটওয়্যারে **OpenAI Login / Key তৈরি** বাটন আছে। Browser-এ Gmail দিয়ে OpenAI login করে key একবার Paste ও Save করলে সেটি Windows Credential Manager-এ নিরাপদে থাকে; পরবর্তীবার আর key দিতে হয় না। Gmail password সফটওয়্যার সংগ্রহ করে না।

সম্পূর্ণ ব্যবহারবিধি: [README_BN.md](README_BN.md)
