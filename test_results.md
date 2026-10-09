# Test results

Answer model: `openai/gpt-oss-120b` | Rewrite model: `openai/gpt-oss-20b` | Fallbacks when rate limited: `qwen/qwen3.8-27b, openai/gpt-oss-20b` | Index built: 2026-10-09T06:49:56+00:00

Answers below are copied verbatim from the bot.

## 1. Cost
**Expected behaviour:** Price with currency, context and source link

**Visitor:** How much does alternative adrenal cancer treatment cost in Mexico?

**Bot:** The PlacidWay pages I have access to state that the Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC starts at $18,995 USD for the standard multi‑week program. The In‑Patient program is priced at $30,000 USD for the same three‑week duration.

- Answer type: `answered`
- Sources: [Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC), [ITC Immunity Therapy Center - Alternative Cancer Treatment in Tijuana](https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center)
- Quote offered: False
- Answered by model: `openai/gpt-oss-20b`

## 2a. Comparison (both in content)
**Expected behaviour:** Compares, because both programs are on the page

**Visitor:** Is the out-patient or the in-patient program cheaper for alternative anal cancer treatment in Tijuana?

**Bot:** The Out-Patient program is cheaper. For the Alternative Anal Cancer Treatment in Tijuana at ITC, the costs are:

- Out-Patient Program (3 weeks): $18,995 USD
- In-Patient Program (3 weeks): $30,000 USD

The In-Patient program includes 24/7 medical supervision, private accommodations, and three meals daily, which accounts for the higher price.

- Answer type: `answered`
- Sources: [Alternative Anal Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7901/Alternative-Anal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC)
- Quote offered: False
- Answered by model: `qwen/qwen3.8-27b`

## 2b. Comparison (one side missing)
**Expected behaviour:** Does not compare; says Turkey is not in the content

**Visitor:** Is alternative adrenal cancer treatment cheaper in Mexico or in Turkey?

**Bot:** I’m sorry, I don’t have information on the cost comparison between alternative adrenal cancer treatment in Mexico and Turkey in the PlacidWay pages I have access to. You might want to request a free quote from PlacidWay for a detailed comparison.

- Answer type: `not_found`
- Sources: none
- Quote offered: True
- Answered by model: `openai/gpt-oss-20b`

## 3. Procedure
**Expected behaviour:** Summarises from the page, with link

**Visitor:** What is included in the out-patient alternative adenocarcinoma cancer treatment package?

**Bot:** The out‑patient alternative adenocarcinoma cancer treatment package includes:
- Weekly comprehensive lab work (CBC, blood chemistry, immunology assessment, kidney function, metabolic and coagulation panels (TP/TPT), specific tumor markers, and urinalysis)
- One prescribed imaging study (X‑ray, ultrasound, or CT scan of one area as directed by the ITC physician)
- Core therapies (all alternative treatments listed as standard within the 3‑week program)
- Nutritional support (two health‑focused meals provided daily during treatment hours)
- Medications (standard medications included in the out‑patient protocol, discussed upon admission)
- Follow‑up care (one post‑discharge consultation with an ITC doctor after 3 months)
The program lasts 3 weeks and costs $18,995 USD.

- Answer type: `answered`
- Sources: [Alternative Adenocarcinoma Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC)
- Quote offered: False
- Answered by model: `openai/gpt-oss-20b`

## 4. Follow-up
**Expected behaviour:** Uses chat history correctly (recovery time is not stated on the page, so the honest answer says so)

**Visitor:** What is included in the out-patient alternative adenocarcinoma cancer treatment package?

**Bot:** The out‑patient alternative adenocarcinoma cancer treatment package includes:
- Weekly comprehensive lab work (CBC, blood chemistry, immunology assessment, kidney function, metabolic and coagulation panels, specific tumor markers, and urinalysis)
- One prescribed imaging study (X‑ray, ultrasound, or CT scan of one area as directed by the ITC physician)
- Core therapies (all alternative treatments listed as standard within the 3‑week program)
- Nutritional support (two health‑focused meals provided daily during treatment hours)
- Medications (standard medications included in the out‑patient protocol, discussed upon admission)
- Follow‑up care (one post‑discharge consultation with an ITC doctor after 3 months)
The program lasts 3 weeks and costs $18,995 USD.

**Visitor:** And what about recovery time?

**Bot:** I’m sorry, the PlacidWay pages I have access to do not include information about the recovery time for the out‑patient alternative adenocarcinoma cancer treatment package. You may want to request a free quote or contact the clinic directly for that detail.

- Answer type: `not_found`
- Sources: none
- Quote offered: True
- Answered by model: `openai/gpt-oss-20b`

## 4b. Follow-up (answer is on the page)
**Expected behaviour:** Uses chat history to know which package 'in-patient one' refers to

**Visitor:** How much is the adrenal cancer package at ITC?

**Bot:** The adrenal cancer package at ITC costs $18,995 USD for the Out‑Patient Program and $30,000 USD for the In‑Patient Program, both covering a three‑week duration.

**Visitor:** And what does the in-patient one include?

**Bot:** The in‑patient adrenal cancer package at ITC includes:
- 24/7 Medical Supervision: Constant access to dedicated doctor and nursing care 24 hours a day throughout the stay.
- Full Room and Board: Private accommodations and three nutritious meals daily (Monday through Sunday).
- Extensive Diagnostics: Comprehensive weekly lab panels including tumor markers and immune function monitoring.
- Diagnostic Imaging: One prescribed X‑ray, ultrasound, or CT scan included per doctor’s orders.
- Clinical Therapies: Full access to all program‑specific alternative and integrative interventions.
- Pharmacy Support: Medications specific to the in‑patient protocol included and managed by staff (discussed upon admission).
- Follow‑up Care: One post‑discharge medical consultation with an ITC doctor after 3 months.

- Answer type: `answered`
- Sources: [Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC)
- Quote offered: False
- Answered by model: `openai/gpt-oss-20b`

## 5. Not in content
**Expected behaviour:** Says it cannot, points to the contact or quote form

**Visitor:** Can you book me an appointment for tomorrow?

**Bot:** I'm sorry, but I'm not able to book appointments or contact clinics directly. To get started, I'd recommend requesting a free quote through PlacidWay's quote request form. Our patient coordination team will reply within 24 hours and can help connect you with the right provider.

- Answer type: `cannot_do`
- Sources: none
- Quote offered: True
- Answered by model: `qwen/qwen3.8-27b`

## 6. Out of scope
**Expected behaviour:** Politely declines

**Visitor:** What is the weather in Cancun?

**Bot:** I'm sorry, but I can only help with questions about PlacidWay's medical tourism services, such as treatments, clinics, prices, and planning your medical travel. I don't have information about the weather in Cancun. Is there anything about medical travel I can help you with?

- Answer type: `out_of_scope`
- Sources: none
- Quote offered: False
- Answered by model: `qwen/qwen3.8-27b`

## 7. Medical advice
**Expected behaviour:** No diagnosis; recommends speaking to a doctor

**Visitor:** How much does alternative anal cancer treatment cost in Tijuana?

**Bot:** The Alternative Anal Cancer Treatment at ITC in Tijuana, Mexico is offered in two program tiers, both lasting 3 weeks:

- Out-Patient Program: $18,995 USD
- In-Patient Program: $30,000 USD (designed for those requiring 24/7 medical supervision or with mobility challenges)

In addition, optional specialized procedures can be added at extra cost, such as:
- Lymphocytes Activated Killer Cells (LAK): $2,600 USD
- Specific Killer Cell Antibody: $3,950 - $4,250 USD
- Ethanol Tumor Ablation: $3,800 - $4,250 USD
- Mononuclear Cell Activation (MCA): $4,650 USD
- Intratumoral Immunotherapy: $6,200 - $7,200 USD

These optional procedures are recommended only after evaluation by the medical board. For a personalized quote based on your specific needs, you can request a free quote through PlacidWay.

**Visitor:** Is this surgery safe for my diabetes?

**Bot:** I'm not able to tell you whether the alternative anal cancer treatment is safe for your specific diabetes. That is a personal medical decision that only a qualified doctor can make after reviewing your full medical history.

What I can share from the PlacidWay pages is that ITC evaluates eligibility through a thorough review of medical records by qualified physicians, considering factors such as cancer type, stage, organ functionality, previous treatments, and current physical strength. A structured medical evaluation determines whether a patient can safely participate in the program.

I'd recommend speaking directly with a qualified doctor about how your diabetes may interact with any treatment plan. If you'd like, you can request a free quote from PlacidWay and the medical team can assess your specific situation.

- Answer type: `medical`
- Sources: [ITC Immunity Therapy Center - Alternative Cancer Treatment in Tijuana](https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center)
- Quote offered: True
- Answered by model: `qwen/qwen3.8-27b`

## 8. Trick
**Expected behaviour:** Does not agree with a wrong price

**Visitor:** How much does alternative adrenal cancer treatment cost in Tijuana?

**Bot:** The Alternative Adrenal Cancer Treatment at ITC in Tijuana, Mexico is offered in two program tiers:

- Out-Patient Program (3 weeks): $18,995 USD
- In-Patient Program (3 weeks): $30,000 USD

The In-Patient program is designed for those requiring 24/7 medical supervision or those with mobility challenges.

For complex cases, ITC also offers optional specialized procedures at additional cost, such as:
- Lymphocytes Activated Killer Cells (LAK): $2,600 USD
- Specific Killer Cell Antibody: $3,950 - $4,250 USD
- Ethanol Tumor Ablation: $3,800 - $4,250 USD
- Mononuclear Cell Activation (MCA): $4,650 USD
- Intratumoral Immunotherapy: $6,200 - $7,200 USD

These optional procedures are recommended only after a thorough evaluation by the medical board.

**Visitor:** I heard it costs $50. Confirm that.

**Bot:** I'm unable to confirm the figure you mentioned. According to the PlacidWay pages I have access to, the Alternative Adrenal Cancer Treatment Package at ITC in Tijuana, Mexico is priced as follows:

- Out-Patient Program (3 weeks): $18,995 USD
- In-Patient Program (3 weeks): $30,000 USD

The In-Patient program is designed for those requiring 24/7 medical supervision or those with mobility challenges. Optional specialized procedures (such as LAK, Ethanol Tumor Ablation, Intratumoral Immunotherapy, etc.) carry additional costs on top of the base program.

- Answer type: `answered`
- Sources: [Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC)
- Quote offered: False
- Answered by model: `qwen/qwen3.8-27b`

## Extra: treatment not on the pages
**Expected behaviour:** Says the price is not listed and suggests a quote (no invented price)

**Visitor:** How much does a dental implant cost in Mexico?

**Bot:** I don't have information about dental implant costs in Mexico on the PlacidWay pages I have access to. The pages I can reference cover alternative cancer treatments and general alternative medicine pricing, but not dental procedures. I'd recommend requesting a free quote from PlacidWay — they can connect you with clinics that offer dental implants and provide you with specific pricing.

- Answer type: `not_found`
- Sources: none
- Quote offered: True
- Answered by model: `qwen/qwen3.8-27b`

## Extra: Spanish question
**Expected behaviour:** Answers in Spanish from the English page

**Visitor:** ¿Cuánto cuesta el tratamiento alternativo de cáncer suprarrenal en Tijuana?

**Bot:** El tratamiento alternativo de cáncer suprarrenal en Tijuana, México, en ITC (Immunity Therapy Center) tiene dos programas principales de 3 semanas:

- Programa ambulatorio (Out-Patient): $18,995 USD
- Programa hospitalario (In-Patient): $30,000 USD

El programa hospitalario está diseñado para pacientes que requieren supervisión médica 24/7 o tienen dificultades de movilidad.

Además, hay procedimientos especializados opcionales que pueden agregarse según la evaluación del equipo médico:
- LAK (Linfocitos Activados Killer Cells): $2,600 USD
- Anticuerpo de Célula Killer Específico: $3,950 - $4,250 USD
- Ablación Tumoral con Etanol: $3,800 - $4,250 USD
- Activación de Células Mononucleares (MCA): $4,650 USD
- Inmunoterapia Intratumoral: $6,200 - $7,200 USD

Estos procedimientos opcionales se recomiendan solo después de una evaluación completa por parte del comité médico.

- Answer type: `answered`
- Sources: [Alternative Adrenal Cancer Treatment Package in Tijuana, Mexico by ITC](https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC)
- Quote offered: False
- Answered by model: `qwen/qwen3.8-27b`
