# Bangla Subtitle Studio V4.0.0 — Professional Timeline Editor

## V4.0.0-এর নতুন Professional Video Timeline

- আগের V3.5-এর Subtitle, বহু ভাষার Translate, Voice Translate, Text To Voice, Organic Voice, Avro, Logo ও Color—সব একইভাবে রাখা হয়েছে।
- নতুন `Media Bin` থেকে একসঙ্গে একাধিক Video, Audio ও Image Import করা যায়।
- Video-গুলো V1 layer-এ পরপর বসানো অথবা Playhead-এর জায়গায় নতুন V2/V3 layer-এ বসানো যায়।
- Video-এর original audio linked থাকে; video move, trim বা split করলে audio-ও একইভাবে পরিবর্তিত হয়।
- আলাদা Audio Import করলে A1, A2, A3… layer নিজে তৈরি হয়।
- Clip মাউস দিয়ে বামে/ডানে টানা, দুই পাশ trim, Playhead-এ split, delete এবং `Ripple Delete` দিয়ে ফাঁকা জায়গা বন্ধ করা যায়।
- Video/Audio layer Add/Remove, Lock, Hide ও Mute করা যায়।
- Clip-এর Start, Source In, Duration, Volume, Fade In ও Fade Out সংখ্যা দিয়ে নিয়ন্ত্রণ করা যায়।
- Preview-তে সম্পূর্ণ Timeline দেখা যায়; Play করলে দ্রুত cached Timeline Preview তৈরি হয়।
- Final Export-এ সব visible video/image layer, unmuted audio layer, Subtitle, Logo ও Color এক MP4-তে তৈরি হয়।
- পুরোনো V2/V3 project খুলবে; V4 project-এ Media, Track, Clip ও সব Timeline settings Save থাকবে।

### খুব সহজ ব্যবহার

১. `+ Video` দিয়ে video দিন—প্রথম video V1 এবং তার audio A1-এ আসবে।
২. আরেকটি video দিলে V1-এর শেষে বসবে; আলাদা layer চাইলে Media Bin থেকে সেটি নির্বাচন করে `Add New Layer` চাপুন।
৩. `+ Audio` দিলে প্রতিটি আলাদা audio নতুন A-layer-এ আসবে।
৪. Clip টেনে সরান; পাশের handle টেনে trim করুন; লাল Playhead বসিয়ে `Split` চাপুন।
৫. `Final Timeline Export` চাপুন, file-এর নাম দিন, তারপর `Export Video` চাপুন।

## V3.5.0-এর Organic বাংলা AI Voice

- Installer-এর মধ্যে Offline Organic বাংলা AI model থাকবে; আলাদা download, API key বা টাকা লাগবে না।
- বাংলা নারী ও পুরুষ কণ্ঠ নির্বাচন করা যাবে।
- `Conversation`, `Happy`, `Angry`, `Sad`, `News` ও `Story/Book` model-এর নিজের Emotion style হিসেবে তৈরি হবে—শুধু কৃত্রিম Pitch পরিবর্তন নয়।
- আপনার ১৬GB RAM ব্যবহার করে CPU-তে চলবে; ২GB GPU-এর ওপর নির্ভর করবে না। তাই কিছুটা ধীর হলেও কম্পিউটারে চলার উপযোগী।
- `Voice Engine` থেকে `Organic CPU Offline` অথবা আগের দ্রুত `Microsoft Natural Online` নির্বাচন করা যাবে।
- English, Hindi, Arabic, Urdu এবং দ্রুত বাংলা voice-এর জন্য Online mode আগের মতোই থাকবে।
- Release দেওয়ার আগে install করা EXE দিয়ে আসল বাংলা Storytelling MP3 তৈরি করে পরীক্ষা পাস করানো হয়।

### Organic বাংলা voice তৈরির নিয়ম

১. `Text To Voice` tab খুলুন।
২. `Voice Engine` থেকে `Organic CPU Offline` রাখুন।
৩. বাংলা script লিখে নারী/পুরুষ কণ্ঠ ও Emotion নির্বাচন করুন।
৪. প্রথমে `Voice Preview` শুনুন; তারপর `Text থেকে Voice তৈরি করুন` চাপুন।
৫. প্রথমবার model load হতে একটু সময় দিন—Internet চালু রাখার প্রয়োজন নেই।

## V3.4.0-এর মানবসদৃশ Emotion Voice

- Text To Voice-এ `Natural`, `Happy`, `Loving`, `Angry`, `Sad`, `Serious` ও `Storytelling` বলার ধরন।
- Emotion কতটা হালকা বা শক্তিশালী হবে তার আলাদা `Emotion Strength` control।
- বাক্যের মাঝে স্বাভাবিক শ্বাস ও ছোট বিরতি; দীর্ঘ script আর একটানা সমান সুরে পড়বে না।
- সম্পূর্ণ MP3 তৈরির আগে `১০ সেকেন্ড Voice Preview` শুনে Voice ID ও Emotion পরীক্ষা করা যাবে।
- Software এখন ব্যবহৃত engine পরিষ্কার দেখায়: `Microsoft Natural Voice` অথবা `Google Basic fallback`।
- Microsoft service না চললে Google Basic voice ব্যবহারের সময় সতর্ক করবে, কারণ সেই কণ্ঠ রোবটের মতো শোনাতে পারে।
- উন্নত মানের জন্য Google Basic fallback default-এ বন্ধ; চাইলে checkbox চালু করে ব্যবহার করা যাবে।
- বাংলা, English, Hindi, Arabic ও Urdu, Speed, Pitch এবং আগের সব Subtitle/Voice Translate সুবিধা অক্ষুণ্ণ আছে।
- API key বা প্রতি voice-এর টাকা লাগে না; Natural Voice তৈরির সময় Internet লাগবে।

## V3.3.0-এর নতুন Text To Voice

- Voice Translate-এর পাশে আলাদা **Text To Voice** tab।
- বাংলা, English, Hindi, Arabic ও Urdu script থেকে MP3 voice।
- প্রতিটি ভাষার নারী/পুরুষ **Voice ID** নির্বাচন।
- **Slow/Fast Speed** এবং **Low/High Pitch** control।
- বড় script ছোট বাক্যে তৈরি হয়ে স্বয়ংক্রিয়ভাবে একটি MP3 হবে।
- Natural voice-এর জন্য Internet লাগবে; API key বা প্রতি voice-এর টাকা লাগবে না।

## পরিষ্কার Avro/Banglish

- Roman লেখার মধ্যে বাংলা হসন্ত, কার বা dotted-circle চিহ্ন থাকবে না।
- শুধু English/Roman অক্ষর ও সাধারণ punctuation থাকবে।
- “Bismillahir Rahmanir Rahim Assalamu Alaikum Warahmatullahi” পরিষ্কারভাবে তৈরি হবে।


## V3.3.0-এ একটি বাক্যের জন্য পুরো ভিডিও আর বন্ধ হবে না

- একটি offline অনুবাদ ভুল অক্ষরে হলে পাশের সঠিক বিকল্পটি নেওয়া হবে।
- প্রয়োজন হলে শুধু সেই বাক্যটি আবার অনুবাদ হবে।
- তারপরও সমস্যা হলে internet ছাড়া English-মাধ্যমে দ্বিতীয় চেষ্টা হবে।
- OpenAI/YouTube/ব্যক্তির নামের মতো Roman নাম থাকলেও সঠিক বাংলা বাক্য বাতিল হবে না।
- কঠিন একটি নাম বা বাক্যের জন্য সম্পূর্ণ Voice Translate বন্ধ বা নীরব হবে না।

## V3.3.0-এ স্বাভাবিক বাংলা ব্যাকরণ

- Offline fallback-এর `আপনি কিভাবে? আমি ঠিক আছে।` এখন voice তৈরির আগে `আপনি কেমন আছেন? আমি ঠিক আছি।` হবে।

## V3.2-এ Hindi → বাংলা voice-এর বড় সংশোধন

- ১২ সেকেন্ড পর্যন্ত অনেক কথা একসঙ্গে জোড়া দেওয়া আর হবে না; সর্বোচ্চ ১০টি source শব্দ বা ৫.৫ সেকেন্ডের ছোট phrase হবে।
- অনুবাদ ছোট হলে voice ধীর করে টানা হবে না এবং বড় হলে শেষের শব্দ কেটে ফেলা হবে না।
- প্রতিটি বাংলা phrase সম্পূর্ণ বলার পর মূল ভিডিওর বিরতি রাখা হবে, তারপর পরের phrase সঠিক সময়ে শুরু হবে।
- Hindi recognition-এ অপ্রয়োজনীয় prompt বাদ দেওয়া হয়েছে, যাতে আসল কথার সঙ্গে অন্য লেখা গুলিয়ে না যায়।
- বাংলা target-এর মধ্যে অধিকাংশ Hindi/English অক্ষর থেকে গেলে সেটি দিয়ে ভুল voice তৈরি হবে না।
- Installer প্রকাশের আগে Hindi → বাংলা অর্থ, ছোট phrase এবং চলমান কথার মাঝখানে ২.২ সেকেন্ডের বেশি ভুল নীরবতা নেই—সব পরীক্ষা পাস করতে হবে।

## V3.1-এ সঠিক অনুবাদ ও গতি

- বাংলা voice → English voice
- English voice → বাংলা voice
- বাংলা voice → Hindi voice
- Hindi voice → বাংলা voice
- Hindi voice → English voice
- English voice → Hindi voice
- Voice Translate-এ এখন সম্পূর্ণ বাক্য ধরে Accurate Online Google translation আগে ব্যবহার হবে।
- অনুবাদের লেখা নির্বাচিত ভাষার সঠিক অক্ষরে না এলে software সেটি গ্রহণ করবে না।
- ভিডিওর বাক্যগুলো ছোট সীমিত Google batch-এ যাবে, যাতে দূরের line একসঙ্গে গুলিয়ে না যায়; Google না চললে installer-এর meaning-checked Offline AI নিজে চালু হবে।
- Hindi ও English মূল voice আরও সঠিক ধরতে Whisper Small-এর বদলে উন্নত Whisper Large V3 Turbo Q5_0 যুক্ত হয়েছে।
- সাধারণভাবে বড় Offline translation model চালু করতে হবে না, তাই আগের ৫০% translation ধাপ অনেক দ্রুত হবে।

## V3.0.1-এ connection সমস্যার সমাধান

- Microsoft Natural Voice server connection না নিলে software নিজে থেকে Google Voice চালু করবে।
- ব্যবহারকারীকে কোনো নতুন button চাপতে বা service নির্বাচন করতে হবে না।
- বাংলা, Hindi, English, Arabic, Urduসহ সমর্থিত ভাষায় fallback কাজ করবে।
- Edge voice নির্বাচন হওয়ার পর কোনো বাক্য download ব্যর্থ হলেও সেই বাক্য Google Voice দিয়ে আবার তৈরি হবে।
- Google fallback-এ service-এর default voice ব্যবহৃত হতে পারে; Microsoft voice চললে নারী/পুরুষ নির্বাচন আগের মতো কাজ করবে।
- Installer প্রকাশের আগে packaged software দিয়ে আসল Google বাংলা voice file তৈরি করে পরীক্ষা করা হয়।

বাংলা ভিডিও থেকে সময়সহ বাংলা সাবটাইটেল তৈরি, লেখা সংশোধন, স্টাইল পরিবর্তন, ভিডিওর ওপর লোগো বসানো, কালার ঠিক করা এবং নতুন MP4 Export করার Windows সফটওয়্যার।

## নতুন Voice Translate / Dubbing

- আলাদা `Voice Translate` tab থেকে মূল voice-এর ভাষা এবং নতুন voice-এর ভাষা নির্বাচন করা যাবে।
- Hindi voice → বাংলা voice, বাংলা → English/Hindi/Arabic, Arabic → বাংলা এবং English → বাংলা করা যাবে।
- বাংলা, English, Hindi, Arabic, Urduসহ আগের তালিকার সমর্থিত ভাষাগুলো source ও target হিসেবে ব্যবহার করা যাবে।
- নারী অথবা পুরুষ natural voice নির্বাচন করা যাবে।
- প্রতিটি অনুবাদ করা বাক্যের নতুন voice মূল কথার শুরু, শেষ ও বিরতির সঙ্গে মিলিয়ে বসবে।
- `পুরোনো অডিও Volume` ০% রাখলে মূল ভাষার voice সম্পূর্ণ বন্ধ থাকবে; চাইলে সর্বোচ্চ ৩০% রাখা যাবে।
- translated লেখা স্বয়ংক্রিয়ভাবে Subtitle tab-এ রাখা যাবে, তারপর font/style/position ঠিক করে Export করা যাবে।
- speech recognition ও text translation কম্পিউটারেই হবে। Natural target voice তৈরির সময় Internet লাগবে, কিন্তু API key বা প্রতি ভিডিওর টাকা লাগবে না।

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
- ভিডিও ও অডিও আপনার কম্পিউটারের বাইরে পাঠানো হবে না; Voice Translate-এ শুধু অনুবাদ করা লেখা natural voice service-এ যাবে।
- বাংলা কথার জন্য V2.2-এর নির্ভরযোগ্য Whisper Bengali Medium Q4 model installer-এর মধ্যেই থাকবে।
- Subtitle ভাষা হিসেবে বাংলা Unicode, বাংলা Avro/Banglish, Hindi, English, Arabic, Urdu, Nepali, Punjabi, Tamil, Telugu, Gujarati, Persian, Spanish, French, German, Italian, Portuguese, Russian, Turkish, Chinese, Japanese ও Korean নির্বাচন করা যাবে।
- Hindi/English/Arabicসহ Translation সম্পূর্ণ Offline AI দিয়ে হবে; API key বা Internet লাগবে না।
- Voice-এর পরে subtitle আসার সমস্যা কমাতে subtitle default ০.৩৫ সেকেন্ড আগে দেখানো হবে। এই সময় software থেকে পরিবর্তন করা যাবে।
- কাজ চলার সময় live শতাংশ ও কত সেকেন্ড চলছে তা দেখা যাবে।

## Install করার নিয়ম

১. GitHub Release থেকে `Bangla_Subtitle_Studio_Professional_Timeline_Setup_V4.0.0.exe` download করুন।
২. Download করা file-এ double-click করুন।  
৩. Windows সতর্কতা দেখালে `More info` → `Run anyway` চাপুন।  
৪. Install শেষ হলে Desktop-এর `Bangla Subtitle Studio` icon খুলুন।

আগের version install করা থাকলে সাধারণভাবে V4.0.0 install করুন। পুরোনো version uninstall করার প্রয়োজন নেই।

## Voice Translate করার নিয়ম

১. `ভিডিও দিন` থেকে মূল ভিডিও নির্বাচন করুন।  
২. `Voice Translate` tab খুলুন।  
৩. `মূল voice-এর ভাষা` এবং `নতুন voice-এর ভাষা` নির্বাচন করুন।  
৪. নারী বা পুরুষ কণ্ঠ নির্বাচন করুন।  
৫. শুধু নতুন translated voice চাইলে পুরোনো অডিও Volume ০% রাখুন।  
৬. translated voice-এর ওপর subtitle চাইলে `Translated লেখাগুলো Subtitle হিসেবে প্রস্তুত রাখুন` চালু রাখুন।  
৭. Output file ঠিক করে `Voice Translate শুরু করুন` চাপুন এবং Internet চালু রাখুন।  
৮. কাজ শেষে translated video Preview-তে খুলবে; Subtitle Style ঠিক করে Export করা যাবে।

## Offline Subtitle তৈরির নিয়ম

১. উপরের `ভিডিও দিন` বাটনে ক্লিক করে MP4/MOV/MKV/AVI/WebM ভিডিও দিন।  
২. `সাবটাইটেলের ভাষা` থেকে বাংলা, Avro/Banglish, Hindi, English, Arabic অথবা পছন্দের ভাষা নির্বাচন করুন।  
৩. Generate-এর আগের default timing-এর জন্য `তৈরির সময় Subtitle আগে` ঠিক করুন।  
৪. বিশেষ কোনো নাম বা শব্দ থাকলে ঐচ্ছিক ঘরে লিখুন।  
৫. `Generate Subtitle` ক্লিক করুন।  
৬. কাজ চলার সময় software বন্ধ করবেন না। Internet চালু রাখার প্রয়োজন নেই।  
৭. তৈরি হওয়া কোনো লাইনে double-click করে লেখা বা সময় ঠিক করুন।
৮. পুরো subtitle দেরিতে এলে `Global Sync` থেকে `আগে`, আর বেশি আগে এলে `পরে` চাপুন। এটি বাংলা, Avro, English, Hindi—সব ভাষাতেই কাজ করবে।

Offline AI আপনার কম্পিউটারের CPU ব্যবহার করে। V3.2-তে বাংলা speech-এর জন্য V2.2-এর Bengali Medium model এবং অন্য source ভাষার জন্য Multilingual Whisper Large V3 Turbo model ব্যবহার করা হয়েছে। Voice Translate-এর Online translation সাধারণভাবে দ্রুত; সেটি না চললে Offline fallback-এ অতিরিক্ত সময় লাগবে। কাজ চলার সময় নিচের live সময় বাড়লে software কাজ করছে।

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
- `Offline subtitle পড়া যায়নি`: V3.2 আবার install করুন; SRT reader fix এই সংস্করণেও আছে।
- Microsoft Natural Voice connection না হলে V3.2 নিজে Google Voice ব্যবহার করবে। দুই service-ই ব্যর্থ হলে VPN বন্ধ করে Windows Firewall/Antivirus-এ software-কে Internet access দিন।
- বাংলা অক্ষর box দেখায়: Windows Settings থেকে Bengali language/font support install করুন।
- কথা ভুল লিখেছে: background music কমানো বা পরিষ্কার audio ব্যবহার করা ভালো; ভুল line-এ double-click করে সংশোধন করুন।

## গোপনীয়তা ও খরচ

Subtitle ও source speech recognition আপনার কম্পিউটারেই `whisper.cpp` model দিয়ে তৈরি হয়। কোনো API account, API key, billing অথবা recurring fee নেই। Subtitle, logo, color correction ও final video Export স্থানীয়ভাবে সম্পন্ন হয়। Voice Translate-এর natural speech বানাতে শুধু অনুবাদ করা text Internet-এর voice service-এ পাঠানো হয়; মূল video বা audio পাঠানো হয় না।
