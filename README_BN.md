# Bangla Subtitle Studio V1

বাংলা ভিডিও থেকে ইন্টারনেটের মাধ্যমে সময়সহ বাংলা সাবটাইটেল তৈরি, লেখা সংশোধন, স্টাইল পরিবর্তন, ভিডিওর ওপর লোগো বসানো, কালার ঠিক করা এবং নতুন MP4 Export করার Windows সফটওয়্যার।

## সবচেয়ে সহজে চালানোর নিয়ম

১. ZIP file-টি Extract করুন।  
২. `INSTALL_AND_RUN.bat`-এ double-click করুন।  
৩. প্রথমবার Internet চালু রাখুন। প্রয়োজন হলে এটি Python, FFmpeg ও ছোট একটি প্রয়োজনীয় package install করবে।  
৪. পরেরবার শুধু `START_APP.bat` চালালেই হবে।

Windows-এর SmartScreen সতর্কতা এলে `More info` → `Run anyway` ব্যবহার করতে হতে পারে।

## Subtitle তৈরির নিয়ম

১. উপরের `ভিডিও দিন` বাটনে ক্লিক করে MP4/MOV/MKV/AVI/WebM ভিডিও দিন।  
২. প্রথমবার `① OpenAI Login / Key তৈরি` চাপুন, Browser-এ Gmail দিয়ে OpenAI login করে নতুন API key Copy করুন।  
৩. Key-টি software-এর ঘরে Paste করে `② Key পরীক্ষা ও Save` চাপুন। এটি Windows Credential Manager-এ নিরাপদে Save হবে; পরেরবার আর দিতে হবে না।  
৪. ভিডিওর ভাষা `বাংলা` রাখুন।  
৫. `Generate Subtitle` ক্লিক করুন।  
৬. তৈরি হওয়া কোনো লাইনে double-click করে বাংলা লেখা, সময় বা দ্বিতীয় ভাষা ঠিক করুন।

দীর্ঘ ভিডিও সফটওয়্যার নিজে নয় মিনিটের ছোট অডিও অংশে ভাগ করে পাঠায়। ফলে প্রতিটি upload ২৫ MB সীমার অনেক নিচে থাকে। ইন্টারনেট ও API balance প্রয়োজন। ChatGPT subscription এবং OpenAI API billing আলাদা।

## Subtitle Style

- বাংলা font নির্বাচন
- লেখার size, bold, outline, shadow
- মূল লেখা, দ্বিতীয় ভাষা, outline ও background-এর রং
- ওপরে, মাঝখানে বা নিচে অবস্থান
- প্রতি লাইনের সর্বোচ্চ অক্ষর
- দ্বিতীয় ভাষা/অনুবাদের ঐচ্ছিক লাইন
- SRT Import এবং SRT Save

Windows-এ বাংলা লেখার জন্য `Nirmala UI` আগে থেকেই থাকে। চাইলে `SolaimanLipi`, `Kalpurush` বা অন্য বাংলা font Windows-এ install করে সফটওয়্যার থেকে নির্বাচন করতে পারবেন।

## Logo Layer

- PNG/JPG/WebP লোগো দেওয়া
- Preview-এর ওপর মাউস দিয়ে টেনে যেকোনো জায়গায় বসানো
- size ও opacity পরিবর্তন
- নয়টি ready position
- পুরো ভিডিও অথবা নির্দিষ্ট শুরু/শেষ সময়

স্বচ্ছ background-এর জন্য PNG logo সবচেয়ে ভালো।

## Video Color

Ready collection: `Natural`, `Warm`, `Cool`, `Cinematic`, `Vivid`, `B&W`।  
Manual controls: Brightness, Contrast, Saturation, Temperature ও Tint।

## Final Export

`Export` tab থেকে output file, quality নির্বাচন করে `Export Video` ক্লিক করুন। মূল ভিডিও অক্ষত থাকবে; subtitle, logo ও color-সহ নতুন MP4 তৈরি হবে।

- `High`: বেশি মান, বড় file
- `Balanced`: YouTube-এর জন্য উপযুক্ত default
- `Small`: কম file size

## Project Save

`.bssproject` file-এ subtitle, style, logo position, color ও output setting save হয়। API key কখনো project-এ রাখা হয় না। ভিডিও বা লোগো অন্য folder-এ সরিয়ে ফেললে project খুলে সেগুলো আবার নির্বাচন করতে হবে।

## Windows EXE/Installer তৈরি

Developer বা পরবর্তী version তৈরির জন্য:

১. `BUILD_WINDOWS_EXE.bat` চালান।  
২. তৈরি হওয়া app থাকবে `dist\Bangla Subtitle Studio\`-এ।  
৩. Inno Setup থাকলে `BanglaSubtitleStudio.iss` compile করে `installer\Bangla_Subtitle_Studio_Setup_V1.exe` তৈরি করা যাবে।

## সাধারণ সমস্যা

- `API key সঠিক নয়`: নতুন/সঠিক API key দিন।
- `API limit বা balance শেষ`: OpenAI API billing/usage পরীক্ষা করুন।
- `FFmpeg পাওয়া যায়নি`: Internet চালু রেখে `INSTALL_AND_RUN.bat` আবার চালান।
- বাংলা অক্ষর box দেখায়: Windows Settings থেকে Bengali language/font support install করুন অথবা বাংলা font install করুন।
- কথা ভুল লিখেছে: background music কমান, পরিষ্কার audio ব্যবহার করুন এবং line-এ double-click করে সংশোধন করুন।

## গোপনীয়তা

Subtitle তৈরি করার সময় ভিডিও থেকে বানানো অডিও অংশ OpenAI transcription API-তে পাঠানো হয়। API key `.bssproject` file বা সাধারণ text file-এ রাখা হয় না; Windows Credential Manager-এ বর্তমান Windows user-এর জন্য নিরাপদে থাকে এবং software থেকে যেকোনো সময় মুছে দেওয়া যায়। Gmail password software কখনো সংগ্রহ করে না। Logo, color correction ও final video Export আপনার কম্পিউটারেই FFmpeg দিয়ে হয়।
