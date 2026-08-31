# Bangla Subtitle Studio V2.6 — Global Sync ও Roman-only Avro

বাংলা ভিডিও থেকে সময়সহ বাংলা সাবটাইটেল তৈরি, লেখা সংশোধন, স্টাইল পরিবর্তন, ভিডিওর ওপর লোগো বসানো, কালার ঠিক করা এবং নতুন MP4 Export করার Windows সফটওয়্যার।

## গুরুত্বপূর্ণ সুবিধা

- Avro/Banglish নিলে শুধু Roman অক্ষরের এক লাইন থাকবে; নিচে বাংলা লেখা আর থাকবে না।
- Avro ও English-এর প্রতিটি শব্দ বড় ইংরেজি অক্ষর দিয়ে শুরু হবে: `Bismillahir Rahmanir Rahim`।
- নতুন `Global Sync` controller-এর `আগে` অথবা `পরে` বাটনে সম্পূর্ণ subtitle একসঙ্গে সরবে। নতুন করে Generate বা ভাষা নির্বাচন করতে হবে না।
- প্রতি ক্লিকে কত সেকেন্ড সরবে তা ০.০৫–২.০০ সেকেন্ডের মধ্যে ঠিক করা যাবে এবং `Reset` করা যাবে।
- ছোট ASR অংশ একই বাক্য হলে একত্র হবে: `বিসমিল্লাহির রহমানের রাহিম, আপনারা কেমন আছেন`।
- কথার মাঝখানে line কাটার সমস্যা কমাতে speech line এবং ভিডিওতে দেখানোর line বড় করা হয়েছে।

- V2.2-তে ভালো কাজ করা Bengali Medium Q4 model আবার ব্যবহার করা হয়েছে, তাই ভিডিও যা বলবে সেটিই যথাসম্ভব হুবহু বাংলায় লেখা হবে।
- Voice Activity Detection ভিডিওর শুরু থেকেই মানুষের কথা খুঁজবে; music বা silence-এর কারণে এক মিনিট পরে subtitle শুরু হওয়ার সমস্যা কমাবে।
- প্রতিটি ছোট speech line-এর আসল সময় নেওয়া হবে; বড় line ভাগ করে আন্দাজের সময় দেওয়া হবে না।
- Hindi/English/Arabicসহ অন্য ভাষায় দুইটি translation বানিয়ে দুটিকেই আবার বাংলায় ফিরিয়ে অর্থ মিলিয়ে সবচেয়ে সঠিকটি রাখা হবে।
- `আসসালামু আলাইকুম`-এর মতো গুরুত্বপূর্ণ greeting অনুবাদে হারিয়ে যাবে না।
- V2.4.1-এর SRT reader fix-টিও রাখা হয়েছে।
- Subtitle তৈরির জন্য কোনো API key লাগবে না।
- OpenAI balance বা মাসিক subscription লাগবে না।
- Internet ছাড়াই যত খুশি subtitle তৈরি করা যাবে।
- ভিডিও ও অডিও আপনার কম্পিউটারের বাইরে পাঠানো হবে না।
- বাংলা কথার জন্য V2.2-এর নির্ভরযোগ্য Whisper Bengali Medium Q4 model installer-এর মধ্যেই থাকবে।
- Subtitle ভাষা হিসেবে বাংলা Unicode, বাংলা Avro/Banglish, Hindi, English, Arabic, Urdu, Nepali, Punjabi, Tamil, Telugu, Gujarati, Persian, Spanish, French, German, Italian, Portuguese, Russian, Turkish, Chinese, Japanese ও Korean নির্বাচন করা যাবে।
- Hindi/English/Arabicসহ Translation সম্পূর্ণ Offline AI দিয়ে হবে; API key বা Internet লাগবে না।
- Voice-এর পরে subtitle আসার সমস্যা কমাতে subtitle default ০.৩৫ সেকেন্ড আগে দেখানো হবে। এই সময় software থেকে পরিবর্তন করা যাবে।
- কাজ চলার সময় live শতাংশ ও কত সেকেন্ড চলছে তা দেখা যাবে।

## Install করার নিয়ম

১. GitHub Release থেকে `Bangla_Subtitle_Studio_Sync_Avro_Setup_V2.6.exe` download করুন।  
২. Download করা file-এ double-click করুন।  
৩. Windows সতর্কতা দেখালে `More info` → `Run anyway` চাপুন।  
৪. Install শেষ হলে Desktop-এর `Bangla Subtitle Studio` icon খুলুন।

আগের version install করা থাকলে সাধারণভাবে V2.6 install করুন। পুরোনো version uninstall করার প্রয়োজন নেই।

## Offline Subtitle তৈরির নিয়ম

১. উপরের `ভিডিও দিন` বাটনে ক্লিক করে MP4/MOV/MKV/AVI/WebM ভিডিও দিন।  
২. `সাবটাইটেলের ভাষা` থেকে বাংলা, Avro/Banglish, Hindi, English, Arabic অথবা পছন্দের ভাষা নির্বাচন করুন।  
৩. Generate-এর আগের default timing-এর জন্য `তৈরির সময় Subtitle আগে` ঠিক করুন।  
৪. বিশেষ কোনো নাম বা শব্দ থাকলে ঐচ্ছিক ঘরে লিখুন।  
৫. `Generate Subtitle` ক্লিক করুন।  
৬. কাজ চলার সময় software বন্ধ করবেন না। Internet চালু রাখার প্রয়োজন নেই।  
৭. তৈরি হওয়া কোনো লাইনে double-click করে লেখা বা সময় ঠিক করুন।
৮. পুরো subtitle দেরিতে এলে `Global Sync` থেকে `আগে`, আর বেশি আগে এলে `পরে` চাপুন। এটি বাংলা, Avro, English, Hindi—সব ভাষাতেই কাজ করবে।

Offline AI আপনার কম্পিউটারের CPU ব্যবহার করে। V2.6-এ accuracy-কে অগ্রাধিকার দিয়ে V2.2-এর Bengali Medium model ব্যবহার করা হয়েছে, তাই V2.4 Fast model-এর চেয়ে কিছু সময় বেশি লাগতে পারে। বাংলা Unicode ও Avro সবচেয়ে দ্রুত; অন্য ভাষায় অর্থ যাচাই করার জন্য Translation-এ অতিরিক্ত সময় লাগবে। কাজ চলার সময় নিচের live সময় বাড়লে software কাজ করছে।

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
- `Offline subtitle পড়া যায়নি`: V2.6 আবার install করুন; SRT reader fix এই সংস্করণেও আছে।
- বাংলা অক্ষর box দেখায়: Windows Settings থেকে Bengali language/font support install করুন।
- কথা ভুল লিখেছে: background music কমানো বা পরিষ্কার audio ব্যবহার করা ভালো; ভুল line-এ double-click করে সংশোধন করুন।

## গোপনীয়তা ও খরচ

Subtitle আপনার কম্পিউটারেই `whisper.cpp` ও Bengali fine-tuned Whisper model দিয়ে তৈরি হয়। কোনো API account, API key, billing অথবা recurring fee নেই। Subtitle, logo, color correction ও final video Export সবই স্থানীয়ভাবে সম্পন্ন হয়।
