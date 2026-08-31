# GitHub Build Guide — V2.6 Sync and Avro

Repository-র `main` branch-এ পরিবর্তন গেলে GitHub Actions নিজে থেকে Windows Offline installer তৈরি করে।

Build সম্পন্ন হলে:

১. Repository খুলুন।  
২. ডান পাশের `Releases` থেকে `Bangla Subtitle Studio V2.6 Sync and Avro` খুলুন।  
৩. `Bangla_Subtitle_Studio_Sync_Avro_Setup_V2.6.exe` download করুন।  

এই installer-এর মধ্যে application, Python runtime, FFmpeg, whisper.cpp এবং বাংলা কথার জন্য আলাদাভাবে প্রশিক্ষিত Whisper Bengali Medium Q4 model থাকে। বাংলা mode স্থায়ীভাবে চালু থাকে এবং GitHub build-এ আসল বাংলা voice থেকে বাংলা অক্ষর তৈরি করে পরীক্ষা করা হয়। API key বা অন্য software লাগে না।
