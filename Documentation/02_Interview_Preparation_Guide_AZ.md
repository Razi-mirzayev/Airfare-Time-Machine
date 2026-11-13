# Texniki Müsahibə Bələdçisi (Interview Preparation Guide)
## Layihə: Airfare Time Machine – US Flight Price Analysis

Bu sənəd iş müsahibələrində (Data Analyst / BI Analyst / Junior-Mid Data Scientist) bu layihə haqqında verilə biləcək ən vacib texniki və biznes suallarına səlis, əminliklə cavab verməyin üçün hazırlanmışdır.

---

## 1. Layihənin Qısa Təqdimatı ("Elevator Pitch" – 60 saniyə)

**Sual:** *"GitHub-dakı Airfare Time Machine layihəniz haqqında danışardınız."*

**Cavab:**
> "Bu layihədə ABŞ-ın 16 əsas hab aeroportu və 50 daxili marşrutu üzrə **38.58 milyon fərdi uçuş müşahidəsini** və **1.68 milyon gündəlik qiymət xülasəsini** təhlil etmişəm. Dataset-in əsas özəlliyi odur ki, eyni uçuş reyslərini (`itinerary_id`) uçuşa **180 gün qalmışdan 7 gün qalmışa qədər** hər gün izləyir.
> Layihəni 4 mərhələdə qurmuşam:
> 1. **MySQL 8.0**-da xam məlumatları **3NF + Star Schema** arxitekturasına normallaşdırıb, CTE və Window funksiyaları ilə 10 əsas biznes sualını cavablandırmışam.
> 2. **Python (Pandas, SciPy, Seaborn)** ilə kontekstual outlier analizi və hipotez testləri (`ANOVA`, `Kruskal-Wallis`, `Welch's t-test`) apararaq optimal bilet alış pəncərəsinin uçuşa **31–60 gün (xüsusilə 49 gün) qalmış** olduğunu (`-34.7%` qənaət) və aviaşirkətlərin **21, 14 və 7-ci günlərdə ATPCO tarif siniflərini bağladığını** müəyyən etmişəm.
> 3. **Power BI**-da DAX ölçüləri və Star Schema ilə Executive Dashboard hazırlamışam.
> 4. **Machine Learning** mərhələsində isə `itinerary_id` üzrə qrup izolyasiyası tətbiq edərək **sıfır Data Leakage** ilə Gradient Boosting modeli qurmuşam (`Test R² = 0.515`, `Median Error = $34.70`)."

---

## 2. SQL və Database Dizaynı Sualları

**Sual 1:** *"Niyə xam CSV fayllarını olduğu kimi MySQL-ə yükləmədiniz, 5 cədvəlli sxem yaratdınız?"*
- **Cavab:** Xam `routes.csv` və `daily_fares.csv` fayllarında **Transitive Dependency (3NF pozuntusu)** var idi: şəhər adları (`origin_city`, `destination_city`) və aeroport kodları hər sətirdə təkrarlanırdı. Həmçinin 38.58 milyon sətirdə `'American Airlines'` kimi mətnləri `VARCHAR` olaraq saxlamaq həm disk həcmini şişirdir, həm də `JOIN` və `GROUP BY` sorğularını ləngidir. Ona görə də `dim_airports`, `dim_airlines` (`1 baytlıq TINYINT UNSIGNED airline_id`) və `dim_routes` yaratdıq.

**Sual 2:** *"`daily_fares.csv`-dəki 87 boş (`NULL`) dəyəri necə emal etdiniz?"*
- **Cavab:** Yoxlama zamanı gördüm ki, bütün 87 `NULL` dəyər yalnız `min_nonstop_price_usd` sütunundadır və hamısı `EWR-SFO` (45 gün) və `SFO-EWR` (42 gün) marşrutlarının payına düşür. Həmin günlərdə birbaşa uçuş olmayıb, yalnız tranzit uçuşlar olub. Onları `0` ilə əvəz etsəydik, orta birbaşa uçuş qiymətini süni şəkildə aşağı salardıq; sətirləri silsəydik, həmin günlərin tranzit məlumatlarını itirərdik. Ona görə MySQL-də `NULLIF(@col, '')` ilə həqiqi `NULL`, Python-da isə `has_nonstop_flight` boolean əlaməti kimi saxladıq.

---

## 3. Statistik Analiz və Biznes Tapıntıları Sualları

**Sual 3:** *"Outlier-ləri necə təyin etdiniz və niyə qlobal IQR kifayət deyildi?"*
- **Cavab:** Qlobal IQR-də yuxarı hədd `$402.5` idi. Lakin 236 millik `LAX-LAS` marşrutunda (normal medianı `$118`) `$320`-lıq bilet 3 qat bahalı sıçrayış olduğu halda qlobal IQR onu tutmurdu. Əksinə, 2,580 millik `SFO-JFK` marşrutunda normal `$410`-lıq bileti outlier sayırdı. Ona görə hər marşrutun öz daxilində **Kontekstual (Route-Specific) IQR** hesabladım və 80,574 (`4.79%`) həqiqi qiymət sıçrayışı tapdım.

**Sual 4:** *"Ən vacib 3 biznes tövsiyəniz nə oldu?"*
1. **Diferensial Bronlaşdırma Pəncərəsi:** `<1,500 mil` uçuşlarda bileti uçuşa **31–60 gün qalmış** almaq son dəqiqəyə nisbətən **~$87–$106 (39–41%)**, `>1,500 mil` transkontinental uçuşlarda isə **90–150 gün əvvəl** almaq ən aşağı qiyməti verir.
2. **Həftənin Günü və Saat Optimallaşdırması:** Bazar günü (`$250.79`) uçmaq əvəzinə Çərşənbə axşamı (`$163.19`) və ya Çərşənbə (`$165.75`) uçmaq **35% (`-$87.60`)**, səhər `09:00–12:00` (`$224.48`) əvəzinə axşam `17:00–20:59` (`$198.89`) uçmaq isə əlavə **11.4%** qənaət yaradır.
3. **Məsafə İqtisadiyyatı (`Price per Mile`):** Qısa uçuşlarda (`<500 mil`) hər mil `$0.395`-ə başa gəldiyi halda, uzaq uçuşlarda (`>1,500 mil`) `$0.110`-a düşür (`Spearman rho = -0.929`).

---

## 4. Machine Learning və Data Leakage Sualları

**Sual 5:** *"Modelinizdə Data Leakage-in qarşısını necə aldınız və niyə R² = 0.515 alındı?"*
- **Cavab:** Üç səviyyədə sızmanın qarşısını aldım:
  1. Eyni günün `min_price_usd` və `max_price_usd` sütunlarını qətiyyən istifadə etmədim.
  2. `routes.csv`-dəki ümumi `median_price_usd` sütununu çıxardım (yalnız fiziki `distance_miles` saxladım).
  3. Ən əsası: eyni `itinerary_id` fərqli axtarış günlərində təkrarlandığı üçün adi təsadüfi bölgü eyni reysi həm Train, həm Test dəstinə salırdı. Mən **`itinerary_id` üzrə Group-Isolated Split** etdim ki, Test dəstindəki bütün reyslər model üçün 100% görünməmiş olsun.
  - Yalnız açıq cədvəl məlumatları ilə (təyyarənin anlıq doluluq faizi — *Cabin Load Factor* — olmadan) qiymət variasiyasının **51.5%-ni** izah etmək və **Median `$34.70` xəta** almaq sızmasız, real istehsalat nəticəsidir.
