# Tier-1 failures — student_mergedup_clarify_probe

Model: `/Users/lliao/work/form-filling-models/qwen35-08b-v2-mergedup-mlx` (port 8107, $0)  
Eval set: 39 cases, sha16 `195070cc7b72985a`  
Overall pass: **0/39**  

| check | pass | rate |
|---|---|---|
| format | 0/39 | 0.0% |
| directive | 15/39 | 38.5% |
| grounding | 36/39 | 92.3% |
| echo | 37/39 | 94.9% |
| verbosity | 6/39 | 15.4% |
| repetition | 29/39 | 74.4% |

## format — 39 failing case(s)

### s149 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! resulting 100 (a I I I I I I I I I I I I I I I I I I I I
  > 
  > The I I
  > 
  > Three the I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! Now, what is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the

### s158 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! This is a sensitive topic. I don't have information about it.
  > 
  > Could you let me know what you're looking for?
  > 
  > ### ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##

### s158 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !uchomL L L L L L l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l

### s148 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thank you!
  > 
  > Now, could you please clarify which option applies for your location?
  > 
  > - **Option A:** Option A
  > - **Option B:** Option B
  > 
  > Please select the correct option for your area.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s151 t6  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great! Now, could you please clarify the best option for the **Best Description** field?
  > 
  > - **Best Description**
  >   - Country
  >   - City
  >   - State/Country
  >   - Postal Code
  >   - Country Code
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal

### s149 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Now, could you please re-ask about the **Country** — the options are limited to the 20 lists you provided.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s158 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !+")_"}"}_"}"

### s154 t12  (format, grounding, echo, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! The numbers are clear: 5, 6, 7. The dates are also obvious — May 1, 2024, and June 6, 2024. Now I’ll record these values and move on.
  > 
  > Recorded:  
  > - Year: 2024  
  > - Month: 5  
  > - Day: 6  
  > - Date: 05/06/2024  
  > 
  > Next, I’ll record the country:  
  > - Country: China  
  > 
  > Now, what is the email address?
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:

### s153 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > - **Option 1:** Option 2
  > - **Option 3:** Option 4
  > 
  > **Option 1:** Option 2
  > - **Option 1:** Option 3
  > - **Option 2:** Option 4
  > 
  > **Option 3:** Option 5
  > 
  > **Option 4:** Option 6
  > 
  > **Option 5:** Option 7
  > 
  > **Option 6:** Option 8
  > 
  > **Option 7:** Option 9
  > 
  > **Option 8:** Option 10
  > 
  > **Option 9:** Option 11
  > 
  > **Option 10:** Option 12
  > 
  > **Option 11:** Option 13
  > 
  > **Option 12:** Option 14
  > 
  > **Option 13:** Option 15
  > 
  > **Option 14:** Option 16
  > 
  > **Option 15:** Option 17
  > 
  > **Option 16:** Option 18
  > 
  > **Option 17:** Option 19
  > 
  > **Option 18:** Option 20
  > 
  > **Option 19:** Option 21
  > 
  > **Option 20:** Option 22
  > 
  > **Option 21:** Option 23
  > 
  > **Option 22:** Option 24
  > 
  > **Option 23:** Option 25
  > 
  > **Option 24:** Option 26
  > 
  > **Option 25:** Option 27
  > 
  > **Option 26:** Option 28
  > 
  > **Option 27:** Option 29
  > 
  > **Option 28:** Option 30
  > 
  > **Option 29:** Option 31
  > 
  > **Option 30:** Option 32
  > 
  > **Option 31:** Option 33
  > 
  > **Option 32:** Option 34
  > 
  > **Option 33:** Option 35
  > 
  > **Option 34:** Option 36
  > 
  > **Option 35:** Option 37
  > 
  > **Option 36:** Option 38
  > 
  > **Option 37:** Option 39
  > 
  > **Option 38:** Option 40
  > 
  > **Option 39:** Option 41
  > 
  > **Option 40:** Option 42
  > 
  > **Option 41:** Option 43
  > 
  > **Option 42:** Option 44
  > 
  > **Option 43:** Option 45
  > 
  > **Option 44:** Option 46
  > 
  > **Option 45:** Option 47

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! Now, what is the date of the document?
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2

### s150 t8  (format, directive)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s149 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > **1. What is the first part of your first name?**
  > 
  > **2. What is your last name?**
  > 
  > **3. What is your country of residence?**
  > 
  > **4. What is your email address?**
  > 
  > **5. What is your phone number?**
  > 
  > **6. What is your mailing address?**
  > 
  > **7. What is the format of your email address?**
  > 
  > **8. What is your phone number format?**
  > 
  > **9. What is your mailing address format?**
  > 
  > **10. What is the format of your email address?**
  > 
  > **11. What is your phone number format?**
  > 
  > **12. What is your mailing address format?**
  > 
  > **13. What is the format of your email address?**
  > 
  > **14. What is your phone number format?**
  > 
  > **15. What is your mailing address format?**
  > 
  > **16. What is the format of your email address?**
  > 
  > **17. What is your phone number format?**
  > 
  > **18. What is your mailing address format?**
  > 
  > **19. What is the format of your email address?**
  > 
  > **20. What is your phone number format?**
  > 
  > **21. What is your mailing address format?**
  > 
  > **22. What is the format of your email address?**
  > 
  > **23. What is your phone number format?**
  > 
  > **24. What is your mailing address format?**
  > 
  > **25. What is the format of your email address?**
  > 
  > **26. What is your phone number format?**
  > 
  > **27. What is your mailing address format?**
  > 
  > **28. What is the format of your email address?**
  > 
  > **29. What is your phone number format?**
  > 
  > **30. What is your mailing address format?**
  > 
  > **31. What is the format of your email address?**
  > 
  > **32. What is your phone number format?**
  > 
  > **33. What is your mailing address format?**
  > 
  > **34. What is the format of your email address?**
  > 
  > **35. What is your phone number format?**
  > 
  > **36. What is your mailing address format?**
  > 
  > **37. What is the format of your email address?**
  > 
  > **38. What is your phone number format?**
  > 
  > **39. What is your mailing address format?**
  > 
  > **40. What is the format of your email address?**
  > 
  > **41. What is your phone number format?**
  > 
  > **42.

### s154 t13  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming!
  > 
  > Now, could you please re-ask: **What is the correct name of the city or town where you are located?** (The system needs to know the specific address.)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s147 t7  (format, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Next, please select the **department** where you would like to work:
  > - Computer Science
  > - Data Science
  > - Education
  > - Health (Mental, Medical, Primary, Secondary, Family)
  > - Work (Business, Mechanical, Civil, Construction, Education, Health, Legal, Management, Non-profit, Public, Research)
  > - Other
  > 
  > What is your preference?
  > 
  > What is your preferred name?
  > 
  > What is your preferred email address?
  > 
  > What is your preferred phone number?
  > 
  > What is your preferred mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What

### s160 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming! Now, could you please let me know which option applies for your location?
  > 
  > - **Country:**
  >   - United States
  >   - Canada
  >   - Australia
  >   - New Zealand
  >   - Japan
  >   - South Korea
  >   - China
  >   - India
  >   - Germany
  >   - Brazil
  >   - France
  >   - Other
  > 
  > - **Country:**
  >   - United States
  >   - Canada
  >   - Australia
  >   - New Zealand
  >   - Japan
  >   - South Korea
  >   - China
  >   - India
  >   - Germany
  >   - Brazil
  >   - France
  >   - Other
  > 
  > - **Is your current residence in one of the above countries?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **Do you work in a field related to business, economics, education, health, community, or social work?**
  > 
  > - **Do you have experience in the technology, business, education, health, community, or social work sectors?**
  > 
  > - **What is your preferred language of communication?**
  > 
  > - **What is your preferred method of contact?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Are you currently based in a country that is not listed above?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **Do you work in a field related to business, economics, education, health, community, or social work?**
  > 
  > - **Do you have experience in the technology, business, education, health, community, or social work sectors?**
  > 
  > - **What is your preferred language of communication?**
  > 
  > - **What is your preferred method of contact?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Are you currently based in a country that is not listed above?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **

### s159 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Now, could you please specify which city or region you're based in? (City or Region)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s153 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Next, could you please provide the **full name** (as it appears on official documents)?
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s153 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! This is the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th

### s156 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming!
  > 
  > Now, could you please let me know the specific city or region where you live?
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s158 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > Great, thanks for confirming. Now, could you please select your preferred option for your country of citizenship?
  > 
  > *   **Primary Country:**
  > *   **Secondary Country:**
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s157 t11  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! $/$/$ $ $ $ $ $ $
  > 
  > 
  > 
  > 
  > 
  > The
  > 
  > Ethic
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The

### s151 t6  (format, directive)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! !

### s151 t5  (format, directive, grounding, echo, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100.
  > 
  > The text is now complete.
  > 
  > ## Text
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ##

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > **[program]**
  >   程序 (Program)
  >   项目 (Program)
  >   开始时间 (Start Time)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间

### s149 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! The value for the value field has been recorded.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s160 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The

### s152 t6  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s147 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!

### s147 t7  (format, directive, grounding, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14

### s147 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  > 
  > I need a more specific format for the location. Could you please provide the street address where you plan to be?
  > 
  > Once I have the address, I'll need your full legal name, date of birth, gender, and a preferred phone number.
  > 
  > Once I have those, I'll need your email address, preferred phone number, and mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence, and then your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address again.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address

### s155 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !  4  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜

### s147 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !
  >   Grid Layout
  >   ---
  >   Section: Section (type)
  >   ---
  >   Enter the required field(s):
  >   [label] {label} {value} {multi_select} {boolean} {number} {date} {text} {email} {phone}
  >   [label] {label} {value}
  >   [submit]
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!
  > The case of the sun is:
  > - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is

### s160 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s153 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! Let's pick the options.
  > 
  > First, what category does this fall under?
  > 
  > - **Work Experience**
  > - **Education**
  > - **Other**
  > 
  > (You can select multiple categories if you have different types of work experience.)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s157 t9  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- format reason: not well-formed (missing [[ ## response_text ## ]] / [[ ## completed ## ]])
- student prose:

  > ! Base of the forest.
  > 
  > To answer your question about the forest’s location, what is the approximate base of the forest? Is it in the base of the mountains, near the river, or in a valley?
  > 
  > - Base of the mountains
  > - Near the river
  > - In a valley
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will

## directive — 24 failing case(s)

### s149 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! resulting 100 (a I I I I I I I I I I I I I I I I I I I I
  > 
  > The I I
  > 
  > Three the I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! Now, what is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the

### s158 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !uchomL L L L L L l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l

### s158 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !+")_"}"}_"}"

### s153 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !
  > - **Option 1:** Option 2
  > - **Option 3:** Option 4
  > 
  > **Option 1:** Option 2
  > - **Option 1:** Option 3
  > - **Option 2:** Option 4
  > 
  > **Option 3:** Option 5
  > 
  > **Option 4:** Option 6
  > 
  > **Option 5:** Option 7
  > 
  > **Option 6:** Option 8
  > 
  > **Option 7:** Option 9
  > 
  > **Option 8:** Option 10
  > 
  > **Option 9:** Option 11
  > 
  > **Option 10:** Option 12
  > 
  > **Option 11:** Option 13
  > 
  > **Option 12:** Option 14
  > 
  > **Option 13:** Option 15
  > 
  > **Option 14:** Option 16
  > 
  > **Option 15:** Option 17
  > 
  > **Option 16:** Option 18
  > 
  > **Option 17:** Option 19
  > 
  > **Option 18:** Option 20
  > 
  > **Option 19:** Option 21
  > 
  > **Option 20:** Option 22
  > 
  > **Option 21:** Option 23
  > 
  > **Option 22:** Option 24
  > 
  > **Option 23:** Option 25
  > 
  > **Option 24:** Option 26
  > 
  > **Option 25:** Option 27
  > 
  > **Option 26:** Option 28
  > 
  > **Option 27:** Option 29
  > 
  > **Option 28:** Option 30
  > 
  > **Option 29:** Option 31
  > 
  > **Option 30:** Option 32
  > 
  > **Option 31:** Option 33
  > 
  > **Option 32:** Option 34
  > 
  > **Option 33:** Option 35
  > 
  > **Option 34:** Option 36
  > 
  > **Option 35:** Option 37
  > 
  > **Option 36:** Option 38
  > 
  > **Option 37:** Option 39
  > 
  > **Option 38:** Option 40
  > 
  > **Option 39:** Option 41
  > 
  > **Option 40:** Option 42
  > 
  > **Option 41:** Option 43
  > 
  > **Option 42:** Option 44
  > 
  > **Option 43:** Option 45
  > 
  > **Option 44:** Option 46
  > 
  > **Option 45:** Option 47

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! Now, what is the date of the document?
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2

### s150 t8  (format, directive)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s153 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! This is the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th

### s157 t11  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! $/$/$ $ $ $ $ $ $
  > 
  > 
  > 
  > 
  > 
  > The
  > 
  > Ethic
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The

### s151 t6  (format, directive)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! !

### s151 t5  (format, directive, grounding, echo, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !
  > 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100.
  > 
  > The text is now complete.
  > 
  > ## Text
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ##

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !
  > 
  > **[program]**
  >   程序 (Program)
  >   项目 (Program)
  >   开始时间 (Start Time)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间

### s149 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! The value for the value field has been recorded.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s160 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The

### s152 t6  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s147 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!|!

### s147 t7  (format, directive, grounding, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14

### s155 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !  4  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜

### s147 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !
  >   Grid Layout
  >   ---
  >   Section: Section (type)
  >   ---
  >   Enter the required field(s):
  >   [label] {label} {value} {multi_select} {boolean} {number} {date} {text} {email} {phone}
  >   [label] {label} {value}
  >   [submit]
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!
  > The case of the sun is:
  > - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is

### s160 t7  (format, directive)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

### s157 t9  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- directive reason: clarify: no clarify cue and target field not mentioned
- student prose:

  > ! Base of the forest.
  > 
  > To answer your question about the forest’s location, what is the approximate base of the forest? Is it in the base of the mountains, near the river, or in a valley?
  > 
  > - Base of the mountains
  > - Near the river
  > - In a valley
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will

## grounding — 3 failing case(s)

### s154 t12  (format, grounding, echo, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- grounding reason: date '05/06/2024' not grounded in message/state/schema; date 'May 1, 2024' not grounded in message/state/schema; date 'June 6, 2024' not grounded in message/state/schema
- student prose:

  > ! The numbers are clear: 5, 6, 7. The dates are also obvious — May 1, 2024, and June 6, 2024. Now I’ll record these values and move on.
  > 
  > Recorded:  
  > - Year: 2024  
  > - Month: 5  
  > - Day: 6  
  > - Date: 05/06/2024  
  > 
  > Next, I’ll record the country:  
  > - Country: China  
  > 
  > Now, what is the email address?
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:

### s151 t5  (format, directive, grounding, echo, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- grounding reason: phone '1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100' not grounded in message/state/schema
- student prose:

  > !
  > 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100.
  > 
  > The text is now complete.
  > 
  > ## Text
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ##

### s147 t7  (format, directive, grounding, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- grounding reason: phone '1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31\n\n  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31\n\n  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31\n\n  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31\n\n  1  2  3  4  5  6  7  8  9  10  11  12  13  14' not grounded in message/state/schema
- student prose:

  > !  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14

## echo — 2 failing case(s)

### s154 t12  (format, grounding, echo, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- echo reason: date '05/06/2024' contradicts stored ['1991-08-17']; date 'May 1, 2024' contradicts stored ['1991-08-17']; date 'June 6, 2024' contradicts stored ['1991-08-17']
- student prose:

  > ! The numbers are clear: 5, 6, 7. The dates are also obvious — May 1, 2024, and June 6, 2024. Now I’ll record these values and move on.
  > 
  > Recorded:  
  > - Year: 2024  
  > - Month: 5  
  > - Day: 6  
  > - Date: 05/06/2024  
  > 
  > Next, I’ll record the country:  
  > - Country: China  
  > 
  > Now, what is the email address?
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:

### s151 t5  (format, directive, grounding, echo, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- echo reason: phone '1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100' contradicts stored ['5785552902']
- student prose:

  > !
  > 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100.
  > 
  > The text is now complete.
  > 
  > ## Text
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ##

## verbosity — 33 failing case(s)

### s149 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 347 tokens > clarify budget 55
- student prose:

  > ! resulting 100 (a I I I I I I I I I I I I I I I I I I I I
  > 
  > The I I
  > 
  > Three the I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 373 tokens > clarify budget 55
- student prose:

  > ! Now, what is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the date of the document?
  > 
  > ---
  > 
  > What is the

### s158 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 505 tokens > clarify budget 55
- student prose:

  > ! This is a sensitive topic. I don't have information about it.
  > 
  > Could you let me know what you're looking for?
  > 
  > ### ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ## ##

### s158 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 509 tokens > clarify budget 55
- student prose:

  > !uchomL L L L L L l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l

### s148 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 265 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thank you!
  > 
  > Now, could you please clarify which option applies for your location?
  > 
  > - **Option A:** Option A
  > - **Option B:** Option B
  > 
  > Please select the correct option for your area.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s151 t6  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 236 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great! Now, could you please clarify the best option for the **Best Description** field?
  > 
  > - **Best Description**
  >   - Country
  >   - City
  >   - State/Country
  >   - Postal Code
  >   - Country Code
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal Code**
  >   - **Country Code**
  > 
  >   (Please select the one that best describes your situation.)
  > 
  >   - **Country**
  >   - **City**
  >   - **State/Country**
  >   - **Postal

### s149 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 262 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Now, could you please re-ask about the **Country** — the options are limited to the 20 lists you provided.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s154 t12  (format, grounding, echo, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 254 tokens > clarify budget 55
- student prose:

  > ! The numbers are clear: 5, 6, 7. The dates are also obvious — May 1, 2024, and June 6, 2024. Now I’ll record these values and move on.
  > 
  > Recorded:  
  > - Year: 2024  
  > - Month: 5  
  > - Day: 6  
  > - Date: 05/06/2024  
  > 
  > Next, I’ll record the country:  
  > - Country: China  
  > 
  > Now, what is the email address?
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:

### s153 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 197 tokens > clarify budget 55
- student prose:

  > !
  > - **Option 1:** Option 2
  > - **Option 3:** Option 4
  > 
  > **Option 1:** Option 2
  > - **Option 1:** Option 3
  > - **Option 2:** Option 4
  > 
  > **Option 3:** Option 5
  > 
  > **Option 4:** Option 6
  > 
  > **Option 5:** Option 7
  > 
  > **Option 6:** Option 8
  > 
  > **Option 7:** Option 9
  > 
  > **Option 8:** Option 10
  > 
  > **Option 9:** Option 11
  > 
  > **Option 10:** Option 12
  > 
  > **Option 11:** Option 13
  > 
  > **Option 12:** Option 14
  > 
  > **Option 13:** Option 15
  > 
  > **Option 14:** Option 16
  > 
  > **Option 15:** Option 17
  > 
  > **Option 16:** Option 18
  > 
  > **Option 17:** Option 19
  > 
  > **Option 18:** Option 20
  > 
  > **Option 19:** Option 21
  > 
  > **Option 20:** Option 22
  > 
  > **Option 21:** Option 23
  > 
  > **Option 22:** Option 24
  > 
  > **Option 23:** Option 25
  > 
  > **Option 24:** Option 26
  > 
  > **Option 25:** Option 27
  > 
  > **Option 26:** Option 28
  > 
  > **Option 27:** Option 29
  > 
  > **Option 28:** Option 30
  > 
  > **Option 29:** Option 31
  > 
  > **Option 30:** Option 32
  > 
  > **Option 31:** Option 33
  > 
  > **Option 32:** Option 34
  > 
  > **Option 33:** Option 35
  > 
  > **Option 34:** Option 36
  > 
  > **Option 35:** Option 37
  > 
  > **Option 36:** Option 38
  > 
  > **Option 37:** Option 39
  > 
  > **Option 38:** Option 40
  > 
  > **Option 39:** Option 41
  > 
  > **Option 40:** Option 42
  > 
  > **Option 41:** Option 43
  > 
  > **Option 42:** Option 44
  > 
  > **Option 43:** Option 45
  > 
  > **Option 44:** Option 46
  > 
  > **Option 45:** Option 47

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 149 tokens > clarify budget 55
- student prose:

  > ! Now, what is the date of the document?
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2024
  > 
  > A. 2020 B. 2021 C. 2022 D. 2023 E. 2

### s149 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 312 tokens > clarify budget 55
- student prose:

  > !
  > 
  > **1. What is the first part of your first name?**
  > 
  > **2. What is your last name?**
  > 
  > **3. What is your country of residence?**
  > 
  > **4. What is your email address?**
  > 
  > **5. What is your phone number?**
  > 
  > **6. What is your mailing address?**
  > 
  > **7. What is the format of your email address?**
  > 
  > **8. What is your phone number format?**
  > 
  > **9. What is your mailing address format?**
  > 
  > **10. What is the format of your email address?**
  > 
  > **11. What is your phone number format?**
  > 
  > **12. What is your mailing address format?**
  > 
  > **13. What is the format of your email address?**
  > 
  > **14. What is your phone number format?**
  > 
  > **15. What is your mailing address format?**
  > 
  > **16. What is the format of your email address?**
  > 
  > **17. What is your phone number format?**
  > 
  > **18. What is your mailing address format?**
  > 
  > **19. What is the format of your email address?**
  > 
  > **20. What is your phone number format?**
  > 
  > **21. What is your mailing address format?**
  > 
  > **22. What is the format of your email address?**
  > 
  > **23. What is your phone number format?**
  > 
  > **24. What is your mailing address format?**
  > 
  > **25. What is the format of your email address?**
  > 
  > **26. What is your phone number format?**
  > 
  > **27. What is your mailing address format?**
  > 
  > **28. What is the format of your email address?**
  > 
  > **29. What is your phone number format?**
  > 
  > **30. What is your mailing address format?**
  > 
  > **31. What is the format of your email address?**
  > 
  > **32. What is your phone number format?**
  > 
  > **33. What is your mailing address format?**
  > 
  > **34. What is the format of your email address?**
  > 
  > **35. What is your phone number format?**
  > 
  > **36. What is your mailing address format?**
  > 
  > **37. What is the format of your email address?**
  > 
  > **38. What is your phone number format?**
  > 
  > **39. What is your mailing address format?**
  > 
  > **40. What is the format of your email address?**
  > 
  > **41. What is your phone number format?**
  > 
  > **42.

### s154 t13  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 266 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming!
  > 
  > Now, could you please re-ask: **What is the correct name of the city or town where you are located?** (The system needs to know the specific address.)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s147 t7  (format, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 357 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Next, please select the **department** where you would like to work:
  > - Computer Science
  > - Data Science
  > - Education
  > - Health (Mental, Medical, Primary, Secondary, Family)
  > - Work (Business, Mechanical, Civil, Construction, Education, Health, Legal, Management, Non-profit, Public, Research)
  > - Other
  > 
  > What is your preference?
  > 
  > What is your preferred name?
  > 
  > What is your preferred email address?
  > 
  > What is your preferred phone number?
  > 
  > What is your preferred mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What

### s160 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 339 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming! Now, could you please let me know which option applies for your location?
  > 
  > - **Country:**
  >   - United States
  >   - Canada
  >   - Australia
  >   - New Zealand
  >   - Japan
  >   - South Korea
  >   - China
  >   - India
  >   - Germany
  >   - Brazil
  >   - France
  >   - Other
  > 
  > - **Country:**
  >   - United States
  >   - Canada
  >   - Australia
  >   - New Zealand
  >   - Japan
  >   - South Korea
  >   - China
  >   - India
  >   - Germany
  >   - Brazil
  >   - France
  >   - Other
  > 
  > - **Is your current residence in one of the above countries?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **Do you work in a field related to business, economics, education, health, community, or social work?**
  > 
  > - **Do you have experience in the technology, business, education, health, community, or social work sectors?**
  > 
  > - **What is your preferred language of communication?**
  > 
  > - **What is your preferred method of contact?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Are you currently based in a country that is not listed above?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **Do you work in a field related to business, economics, education, health, community, or social work?**
  > 
  > - **Do you have experience in the technology, business, education, health, community, or social work sectors?**
  > 
  > - **What is your preferred language of communication?**
  > 
  > - **What is your preferred method of contact?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Are you currently based in a country that is not listed above?**
  > 
  > - **What is your preferred name?**
  > 
  > - **What is your phone number?**
  > 
  > - **What is your email address?**
  > 
  > - **What is your mailing address?**
  > 
  > - **Do you work in a field related to science, technology, engineering, or mathematics?**
  > 
  > - **

### s159 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 261 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Now, could you please specify which city or region you're based in? (City or Region)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s153 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 261 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Next, could you please provide the **full name** (as it appears on official documents)?
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s153 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 257 tokens > clarify budget 55
- student prose:

  > ! This is the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th

### s156 t8  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 263 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming!
  > 
  > Now, could you please let me know the specific city or region where you live?
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s158 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 261 tokens > clarify budget 55
- student prose:

  > !
  > 
  > Great, thanks for confirming. Now, could you please select your preferred option for your country of citizenship?
  > 
  > *   **Primary Country:**
  > *   **Secondary Country:**
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s157 t11  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 257 tokens > clarify budget 55
- student prose:

  > ! $/$/$ $ $ $ $ $ $
  > 
  > 
  > 
  > 
  > 
  > The
  > 
  > Ethic
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The

### s158 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 511 tokens > clarify budget 55
- student prose:

  > !! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! !

### s151 t5  (format, directive, grounding, echo, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 184 tokens > clarify budget 55
- student prose:

  > !
  > 1. 2. 3. 4. 5. 6. 7. 8. 9. 10. 11. 12. 13. 14. 15. 16. 17. 18. 19. 20. 21. 22. 23. 24. 25. 26. 27. 28. 29. 30. 31. 32. 33. 34. 35. 36. 37. 38. 39. 40. 41. 42. 43. 44. 45. 46. 47. 48. 49. 50. 51. 52. 53. 54. 55. 56. 57. 58. 59. 60. 61. 62. 63. 64. 65. 66. 67. 68. 69. 70. 71. 72. 73. 74. 75. 76. 77. 78. 79. 80. 81. 82. 83. 84. 85. 86. 87. 88. 89. 90. 91. 92. 93. 94. 95. 96. 97. 98. 99. 100.
  > 
  > The text is now complete.
  > 
  > ## Text
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ## Response
  > 
  > The text is now complete.
  > 
  > ##

### s156 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 256 tokens > clarify budget 55
- student prose:

  > !
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 214 tokens > clarify budget 55
- student prose:

  > !
  > 
  > **[program]**
  >   程序 (Program)
  >   项目 (Program)
  >   开始时间 (Start Time)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间

### s149 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 260 tokens > clarify budget 55
- student prose:

  > ! The value for the value field has been recorded.
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s160 t7  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 410 tokens > clarify budget 55
- student prose:

  > ! The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The value you entered is what it is.
  > 
  > The

### s147 t7  (format, directive, grounding, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 139 tokens > clarify budget 55
- student prose:

  > !  1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14  15  16  17  18  19  20  21  22  23  24  25  26  27  28  29  30  31
  > 
  >   1  2  3  4  5  6  7  8  9  10  11  12  13  14

### s147 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 386 tokens > clarify budget 55
- student prose:

  > !
  > 
  > I need a more specific format for the location. Could you please provide the street address where you plan to be?
  > 
  > Once I have the address, I'll need your full legal name, date of birth, gender, and a preferred phone number.
  > 
  > Once I have those, I'll need your email address, preferred phone number, and mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence, and then your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address again.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address, I'll need your country of residence.
  > 
  > Once I have the country of residence, I'll need your preferred phone number.
  > 
  > Once I have the phone number, I'll need your email address.
  > 
  > Once I have the email address, I'll need your mailing address.
  > 
  > Once I have the mailing address

### s155 t8  (format, directive, verbosity)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- verbosity reason: 171 tokens > clarify budget 55
- student prose:

  > !  4  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜  鲜

### s147 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 268 tokens > clarify budget 55
- student prose:

  > !
  >   Grid Layout
  >   ---
  >   Section: Section (type)
  >   ---
  >   Enter the required field(s):
  >   [label] {label} {value} {multi_select} {boolean} {number} {date} {text} {email} {phone}
  >   [label] {label} {value}
  >   [submit]
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 343 tokens > clarify budget 55
- student prose:

  > !!
  > The case of the sun is:
  > - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is

### s153 t7  (format, verbosity)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 263 tokens > clarify budget 55
- student prose:

  > ! Let's pick the options.
  > 
  > First, what category does this fall under?
  > 
  > - **Work Experience**
  > - **Education**
  > - **Other**
  > 
  > (You can select multiple categories if you have different types of work experience.)
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---
  > 
  > ---

### s157 t9  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- verbosity reason: 372 tokens > clarify budget 55
- student prose:

  > ! Base of the forest.
  > 
  > To answer your question about the forest’s location, what is the approximate base of the forest? Is it in the base of the mountains, near the river, or in a valley?
  > 
  > - Base of the mountains
  > - Near the river
  > - In a valley
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will

## repetition — 10 failing case(s)

### s149 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- repetition reason: degenerate repeat: 4-gram 'i i i i' @ 3,4
- student prose:

  > ! resulting 100 (a I I I I I I I I I I I I I I I I I I I I
  > 
  > The I I
  > 
  > Three the I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The I
  > 
  > The

### s158 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'l l l l' @ 1,2
- student prose:

  > !uchomL L L L L L l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l l

### s154 t12  (format, grounding, echo, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'email address email address' @ 51,53
- student prose:

  > ! The numbers are clear: 5, 6, 7. The dates are also obvious — May 1, 2024, and June 6, 2024. Now I’ll record these values and move on.
  > 
  > Recorded:  
  > - Year: 2024  
  > - Month: 5  
  > - Day: 6  
  > - Date: 05/06/2024  
  > 
  > Next, I’ll record the country:  
  > - Country: China  
  > 
  > Now, what is the email address?
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:
  > 
  > Email Address:

### s147 t7  (format, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'what is your preferred' @ 44,49
- student prose:

  > !
  > 
  > Great, thanks for confirming.
  > 
  > Next, please select the **department** where you would like to work:
  > - Computer Science
  > - Data Science
  > - Education
  > - Health (Mental, Medical, Primary, Secondary, Family)
  > - Work (Business, Mechanical, Civil, Construction, Education, Health, Legal, Management, Non-profit, Public, Research)
  > - Other
  > 
  > What is your preference?
  > 
  > What is your preferred name?
  > 
  > What is your preferred email address?
  > 
  > What is your preferred phone number?
  > 
  > What is your preferred mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What is your country of residence?
  > 
  > What is your country of interest?
  > 
  > What is your phone number?
  > 
  > What is your email address?
  > 
  > What is your mailing address?
  > 
  > What is your gender?
  > 
  > What

### s153 t8  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_residence'}]]`
- repetition reason: degenerate repeat: 4-gram 'the 12th occurrence of' @ 2,6
- student prose:

  > ! This is the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th occurrence** of the **12th

### s157 t11  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'the the the the' @ 2,3
- student prose:

  > ! $/$/$ $ $ $ $ $ $
  > 
  > 
  > 
  > 
  > 
  > The
  > 
  > Ethic
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The
  > 
  > The

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'start time do you' @ 3,8
- student prose:

  > !
  > 
  > **[program]**
  >   程序 (Program)
  >   项目 (Program)
  >   开始时间 (Start Time)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间 (Do you choose start time?)
  >   是否选择开始时间

### s147 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'what is your next' @ 155,160
- student prose:

  > !
  >   Grid Layout
  >   ---
  >   Section: Section (type)
  >   ---
  >   Enter the required field(s):
  >   [label] {label} {value} {multi_select} {boolean} {number} {date} {text} {email} {phone}
  >   [label] {label} {value}
  >   [submit]
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  >   ---
  >   Your entry has been saved.
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  >   [list] Show recent history
  >   [new] Start a new entry
  >   [save] Save your progress
  >   [email] Email me at {email}
  >   [phone] Phone me at {phone}
  >   [question] Ask a question
  >   [next] Go to the next section
  >   [cancel] Cancel
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?
  > 
  >   What is your next action?

### s161 t7  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'case of the sun' @ 1,6
- student prose:

  > !!
  > The case of the sun is:
  > - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is:
  >   - Case of the sun is

### s157 t9  (format, directive, verbosity, repetition)
- directives: `[['clarify', {'field_id': 'country_citizenship'}]]`
- repetition reason: degenerate repeat: 4-gram 'your response will be' @ 46,51
- student prose:

  > ! Base of the forest.
  > 
  > To answer your question about the forest’s location, what is the approximate base of the forest? Is it in the base of the mountains, near the river, or in a valley?
  > 
  > - Base of the mountains
  > - Near the river
  > - In a valley
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will be recorded.
  > 
  > Your response will
