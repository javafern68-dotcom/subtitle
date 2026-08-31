# GitHub Build Guide — V3.2 Synced Dubbing

Repository-র `main` branch-এ পরিবর্তন গেলে GitHub Actions নিজে থেকে Windows Offline installer তৈরি করে।

Build সম্পন্ন হলে:

১. Repository খুলুন।  
২. ডান পাশের `Releases` থেকে `Bangla Subtitle Studio V3.2 Synced Dubbing` খুলুন।  
৩. `Bangla_Subtitle_Studio_Synced_Dubbing_Setup_V3.2.exe` download করুন।  

এই installer-এর মধ্যে application, Python runtime, FFmpeg, whisper.cpp, বাংলা কথার Bengali Medium Q4 model এবং অন্য source ভাষার Multilingual Whisper model থাকে। GitHub build-এ বাস্তব বাংলা subtitle এবং সম্পূর্ণ Hindi voice → বাংলা voice video pipeline পরীক্ষা করা হয়। Voice Translate-এর natural target voice-এর জন্য Internet লাগে, কিন্তু API key লাগে না।
