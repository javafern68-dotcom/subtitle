# Bangla Subtitle Studio V2.4.1 — দ্রুত Multilanguage Subtitle (Fixed)

বাংলা ভিডিও থেকে সময়সহ বাংলা সাবটাইটেল তৈরি, লেখা সংশোধন, স্টাইল পরিবর্তন, ভিডিওর ওপর লোগো বসানো, কালার ঠিক করা এবং নতুন MP4 Export করার Windows সফটওয়্যার।

## গুরুত্বপূর্ণ সুবিধা

- V2.4.1-এ নতুন দ্রুত model-এর তৈরি SRT পড়ার সমস্যাটি ঠিক করা হয়েছে; একটি time line ভুল হলেও বাকি subtitle আর নষ্ট হবে না।
- Subtitle তৈরির জন্য কোনো API key লাগবে না।
- OpenAI balance বা মাসিক subscription লাগবে না।
- Internet ছাড়াই যত খুশি subtitle তৈরি করা যাবে।
- ভিডিও ও অডিও আপনার কম্পিউটারের বাইরে পাঠানো হবে না।
- বাংলা কথার জন্য আলাদাভাবে প্রশিক্ষিত দ্রুত Whisper Bengali Small Q5 model installer-এর মধ্যেই থাকবে।
- বাংলা voice দ্রুত Bengali Small model দিয়ে লেখা হবে।
- Subtitle ভাষা হিসেবে বাংলা Unicode, বাংলা Avro/Banglish, Hindi, English, Arabic, Urdu, Nepali, Punjabi, Tamil, Telugu, Gujarati, Persian, Spanish, French, German, Italian, Portuguese, Russian, Turkish, Chinese, Japanese ও Korean নির্বাচন করা যাবে।
- Hindi/English/Arabicসহ Translation সম্পূর্ণ Offline AI দিয়ে হবে; API key বা Internet লাগবে না।
- Voice-এর পরে subtitle আসার সমস্যা কমাতে subtitle default ০.৩৫ সেকেন্ড আগে দেখানো হবে। এই সময় software থেকে পরিবর্তন করা যাবে।
- কাজ চলার সময় live শতাংশ ও কত সেকেন্ড চলছে তা দেখা যাবে।

## Install করার নিয়ম

১. GitHub Release থেকে `Bangla_Subtitle_Studio_Multilanguage_Fixed_Setup_V2.4.1.exe` download করুন।  
২. Download করা file-এ double-click করুন।  
৩. Windows সতর্কতা দেখালে `More info` → `Run anyway` চাপুন।  
৪. Install শেষ হলে Desktop-এর `Bangla Subtitle Studio` icon খুলুন।

আগের version install করা থাকলে সাধারণভাবে V2.4.1 install করুন। পুরোনো version uninstall করার প্রয়োজন নেই।

## Offline Subtitle তৈরির নিয়ম

১. উপরের `ভিডিও দিন` বাটনে ক্লিক করে MP4/MOV/MKV/AVI/WebM ভিডিও দিন।  
২. `সাবটাইটেলের ভাষা` থেকে বাংলা, Avro/Banglish, Hindi, English, Arabic অথবা পছন্দের ভাষা নির্বাচন করুন।  
৩. Subtitle দেরিতে এলে `Subtitle আগে দেখান` ০.৩৫ থেকে ০.৫০ করুন; বেশি আগে এলে কমিয়ে দিন।  
৪. বিশেষ কোনো নাম বা শব্দ থাকলে ঐচ্ছিক ঘরে লিখুন।  
৫. `Generate Subtitle` ক্লিক করুন।  
৬. কাজ চলার সময় software বন্ধ করবেন না। Internet চালু রাখার প্রয়োজন নেই।  
৭. তৈরি হওয়া কোনো লাইনে double-click করে লেখা বা সময় ঠিক করুন।

Offline AI আপনার কম্পিউটারের CPU ব্যবহার করে। V2.4-এর Bengali Small model আগের V2.2 Medium model-এর তুলনায় অনেক ছোট ও দ্রুত। বাংলা Unicode ও Avro সবচেয়ে দ্রুত; অন্য ভাষা নিলে বাংলা লেখা তৈরির পরে Offline Translation-এর জন্য কিছু অতিরিক্ত সময় লাগবে। কাজ চলার সময় নিচে live শতাংশের সঙ্গে সেকেন্ডও বদলাবে—সেকেন্ড বাড়তে থাকলে software কাজ করছে।

## Subtitle Style

- বাংলা font নির্বাচন
- লেখার size, bold, outline ও shadow
- মূল লেখা, দ্বিতীয় ভাষা, outline ও background-এর রং
- ওপরে, মাঝখানে বা নিচে অবস্থান
- প্রতি লাইনের সর্বোচ্চ অক্ষর
- SRT Import ও SRT Save

Windows-এ বাংলা লেখার জন্য `Nirmala UI` আগে থেকেই থাকে। চাইলে `SolaimanLipi`, `Kalpurush` বা অন্য বাংলা font Windows-এ install করে software থেকে নির্বাচন করা যাবে।

## Logo Layer

- PNG/JPG/WebP লোগো
- Preview-এর ওপর মাউস দিয়ে টেনে অবস্থান পরিবর্তন
- Size ও opacity পরিবর্তন
- Ready position
- পুরো ভিডিও অথবা নির্দিষ্ট শুরু/শেষ সময়

স্বচ্ছ background-এর জন্য PNG logo সবচেয়ে ভালো।

## Video Color

Ready collection: `Natural`, `Warm`, `Cool`, `Cinematic`, `Vivid`, `B&W`।  
Manual controls: Brightness, Contrast, Saturation, Temperature ও Tint।

## Final Export

`Export` tab থেকে output file ও quality নির্বাচন করে `Export Video` ক্লিক করুন। মূল ভিডিও অক্ষত থাকবে; subtitle, logo ও color-সহ নতুন MP4 তৈরি হবে।

- `High`: বেশি মান, বড় file
- `Balanced`: YouTube-এর জন্য উপযুক্ত default
- `Small`: কম file size

## Project Save

`.bssproject` file-এ subtitle, style, logo position, color ও output setting save হয়। ভিডিও বা লোগো অন্য folder-এ সরালে project খুলে সেগুলো আবার নির্বাচন করতে হবে।

## সাধারণ সমস্যা

- `Offline বাংলা AI model পাওয়া যায়নি`: V2 Offline installer আবার install করুন।
- কাজ ধীরে হচ্ছে: নিচের “কাজ চলছে” সময় বাড়ছে কি না দেখুন, অন্য ভারী software বন্ধ করুন এবং কাজ শেষ হওয়া পর্যন্ত অপেক্ষা করুন।
- `পর্যাপ্ত RAM` বার্তা: অন্য software বন্ধ করে আবার চেষ্টা করুন।
- `Offline subtitle পড়া যায়নি`: V2.4.1 install করুন; এই সংস্করণে SRT reader fix করা হয়েছে।
- বাংলা অক্ষর box দেখায়: Windows Settings থেকে Bengali language/font support install করুন।
- কথা ভুল লিখেছে: background music কমানো বা পরিষ্কার audio ব্যবহার করা ভালো; ভুল line-এ double-click করে সংশোধন করুন।

## গোপনীয়তা ও খরচ

Subtitle আপনার কম্পিউটারেই `whisper.cpp` ও Bengali fine-tuned Whisper model দিয়ে তৈরি হয়। কোনো API account, API key, billing অথবা recurring fee নেই। Subtitle, logo, color correction ও final video Export সবই স্থানীয়ভাবে সম্পন্ন হয়।
