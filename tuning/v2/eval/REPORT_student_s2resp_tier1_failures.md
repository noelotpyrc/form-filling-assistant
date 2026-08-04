# Tier-1 failures — student_s2resp_responder_tier1_frozen223

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2resp-mlx` (port 8102, $0)  
Eval set: 223 cases, sha16 `2c7678f763a9256b`  
Overall pass: **212/223**  

| check | pass | rate |
|---|---|---|
| format | 223/223 | 100.0% |
| directive | 214/223 | 96.0% |
| grounding | 223/223 | 100.0% |
| echo | 223/223 | 100.0% |
| verbosity | 221/223 | 99.1% |

## directive — 9 failing case(s)

### s147 t14  (directive)
- directives: `[['submit_blocked', ['email', 'phone', 'mailing_address', 'has_work_experience']]]`
- directive reason: submit_blocked: needs can't-submit-yet plus a save/continue offer
- student prose:

  > Thanks for confirming — you're all set!
  > 
  > Just one final thing to keep in mind: if you ever need to change your mind about funding, the available options are Teaching Assistantship, Research Assistantship, Fellowship, and Scholarship. Would you like to select any now, or are you all set?

### s148 t17  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks! Now, are you interested in funding or assistantships (like teaching or research assistantships, fellowships, or scholarships)?

### s149 t13  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks! Now, are you **interested in funding or assistantships** (such as teaching assistantships, research assistantships, fellowships, or scholarships)?

### s150 t13  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks for confirming! Now, **are you interested in funding or assistantships** (such as teaching assistantships, research assistantships, fellowships, or scholarships)?

### s152 t5  (directive)
- directives: `[['reask_pending', 'country_citizenship']]`
- directive reason: reask_pending: field 'country_citizenship' not asked about
- student prose:

  > How's your day going?

### s152 t9  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Great! Now, **are you interested in funding or assistantships?**

### s153 t14  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks for confirming! Now I'll need your **Mailing Address** to complete the application.

### s154 t17  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks! Now I'll need your mailing address to continue with the application. Please provide your full mailing address including street address, city, state/province, postal code, and country.

### s160 t13  (directive)
- directives: `[['terminal', None]]`
- directive reason: terminal: no review/submit invitation
- student prose:

  > Thanks! Now, are you interested in funding or assistantships?

## verbosity — 2 failing case(s)

### s158 t13  (verbosity)
- directives: `[['terminal', None]]`
- verbosity reason: 125 tokens > terminal budget 75
- student prose:

  > Thanks for confirming! All the required information is now complete.
  > 
  > Here's a summary of your application:
  > 
  > - Program of Interest: Computer Science (MS)
  > - Intended Start Term: Spring 2027
  > - Enrollment Type: Full-time
  > - Have you previously applied to Northfield?: Yes
  > - Full Legal Name: Chloe Haddad
  > - Date of Birth: 07/19/1986
  > - Country of Citizenship: United States
  > - Country of Residence: Australia
  > - Email Address: chloe.haddad14@example.com
  > - Phone Number: (989) 555-6398
  > - Mailing Address: 7570 Pine Way, Springfield, CA 24919, United States
  > - Do you have relevant work experience?: Yes
  > - Interested in funding/assistantships?: Yes
  > 
  > All the necessary details have been collected. Please review the summary above and let me know if everything is complete, or let me know if you need any adjustments.

### s161 t13  (verbosity)
- directives: `[['terminal', None]]`
- verbosity reason: 109 tokens > terminal budget 75
- student prose:

  > Thanks for letting me know! I've recorded your preference for funding/assistantships.
  > 
  > All the required information is now complete. Here's a summary of your application:
  > 
  > - Program of Interest: Mechanical Engineering (MS)
  > - Intended Start Term: Fall 2026
  > - Enrollment Type: Part-time
  > - Have you previously applied to Northfield?: Yes
  > - If yes, which year?: 2015
  > - Full Legal Name: Tariq Nguyen
  > - Date of Birth: 04/21/1990
  > - Country of Citizenship: Germany
  > - Country of Residence: South Korea
  > - Email Address: tariq.nguyen71@example.com
  > - Phone Number: (804) 555-8863
  > - Mailing Address: 562 Sunset Dr, Clayton, GA 73902
  > 
  > All fields are complete — you can review the summary and submit your application.
