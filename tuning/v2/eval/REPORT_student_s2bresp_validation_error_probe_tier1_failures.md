# Tier-1 failures — student_s2bresp_validation_error_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-s2bresp-mlx` (port 8103, $0)  
Eval set: 40 cases, sha16 `084f50ce6df3e2fd`  
Overall pass: **24/40**  

| check | pass | rate |
|---|---|---|
| format | 40/40 | 100.0% |
| directive | 24/40 | 60.0% |
| grounding | 39/40 | 97.5% |
| echo | 40/40 | 100.0% |
| verbosity | 40/40 | 100.0% |

## directive — 16 failing case(s)

### s159 t14  (directive)
- directives: `[['fix', 'please re-enter that field.']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > I'm here whenever you need me, no matter the time zone! 😊
  > 
  > To continue, **do you have relevant work experience?**

### s159 t7  (directive)
- directives: `[['fix', 'please re-enter that field.']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > Thanks for confirming! Now I'll need your **country of citizenship**.

### s156 t6  (directive)
- directives: `[['fix', 'please correct your entry (field: dob).']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We've got that — thank you for confirming!
  > 
  > Could you please provide your date of birth in MM/DD/YYYY format?

### s148 t11  (directive, grounding)
- directives: `[['fix', "that value doesn't look right (field: phone)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > Thanks for providing the phone number! Could you please use the format shown (e.g., (555) 555-5555)?

### s156 t9  (directive)
- directives: `[['fix', "that value doesn't look right (field: mailing_address)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > Thanks for providing that! I've recorded your mailing address.

### s154 t3  (directive)
- directives: `[['fix', "something's off with that value."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We've got that! Could you please re-verify the term you'd like to start?

### s155 t12  (directive)
- directives: `[['fix', "that value doesn't look right (field: email)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > I'm not able to complete this application with the email address you provided — it doesn't look like a valid email format. Could you please use a different email address?

### s159 t15  (directive)
- directives: `[['fix', "that value doesn't look right (field: funding_interest)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > I apologize for the confusion — I just need you to provide the value for **funding_interest** (a choice: Yes, No).

### s157 t16  (directive)
- directives: `[['fix', "that value doesn't look right (field: has_work_experience)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We apologize for the inconvenience! We need you to provide a valid phone number (it should be a number, not a string like "(557) 555-6678").

### s154 t9  (directive)
- directives: `[['fix', "that value doesn't look right (field: full_name)."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > Thanks for the correction! Could you please provide your full legal name as it appears on official documents?

### s158 t13  (directive)
- directives: `[['fix', 'please correct your entry (field: funding_interest).']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We apologize for the inconvenience! We're here to help, but the field **funding_interest** still needs to be completed before we can continue.

### s149 t10  (directive)
- directives: `[['fix', 'please re-enter that field.']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We've got that — thank you! Now I'll need your **phone number** to continue.

### s156 t4  (directive)
- directives: `[['fix', "something's off with that value."]]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > Thanks for confirming all the details! I've recorded your start term as Fall 2026, full-time enrollment, and your contact information.
  > 
  > Now, have you previously applied to Northfield University?

### s157 t5  (directive)
- directives: `[['fix', 'please re-enter that field.']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We've hit a validation issue — please re-enter the required field.

### s156 t7  (directive)
- directives: `[['fix', 'please correct your entry (field: country_citizenship).']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We apologize for the inconvenience! We need you to provide your country of citizenship.

### s153 t10  (directive)
- directives: `[['fix', 'the value for phone is invalid (field: phone).']]`
- directive reason: fix: needs an apology plus a re-ask
- student prose:

  > We've got that — the phone number format needs to be adjusted. Could you please provide a valid phone number?

## grounding — 1 failing case(s)

### s148 t11  (directive, grounding)
- directives: `[['fix', "that value doesn't look right (field: phone)."]]`
- grounding reason: phone '555) 555-5555' not grounded in message/state/schema
- student prose:

  > Thanks for providing the phone number! Could you please use the format shown (e.g., (555) 555-5555)?
