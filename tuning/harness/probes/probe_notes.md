## P1

* Ex1, brand new applicant, model hallucinating as returned applicant
* Ex1, temp 0.7 is doing better than temp 0, "Before we dive in, let me also show you what's already saved on your end (in case you need to come back to it later)." which looks like a confusing sentence
* Ex2, text response still confusing, hallucinating where the user return from (we didn't provide any of the info as context)
* Ex3, model is too eager to carry on its job of form filling, rather than just stopping at chitchat level + simply asking a question (what can i help you with)
* Ex4, temp 0.7 hallucinating text like conversation history (User: ..., Assistant: ...)

## P2

* Ex1, temp 0.7 hallucinating a different field value
* Ex2, temp 0.7 hallucinating user as returned user with saved info
* Ex3, temp 0 hallucinating a different program, both temp not aware the program is not possible
* Ex4, temp 0 went ahead to set the field, both temp chose to ask choice for all programs again
* Ex5, model failed to set field when text response confirmed

## P3

* Ex1, temp 0 text confirms but not set the field
* Ex2, model not responding correctly to user's unwillingness to share additional info
* Ex3, temp 0.7 hallucinating has new data
* Ex4, temp 0.7 hallucinating field values
* Ex5, model hallucinating has new data

## P4

* Ex1, model miss end date
* Ex2, temp 0.7 ask the same question again
* Ex3, model hallucinating responses
* Ex4, temp 0 hallucinating work description (15% improvement from nowhere)
* Ex5, model failed to detect has new data, temp 0.7 hallucinating has choice

## P5

* Ex1 seems fine
* Ex2, model uses wrong index for new job
* Ex3, temp 0 got the text response ok, but set field wrong, temp 0.7 failed to start set field
* Ex4, i don't think we have the action for removing, this is a design flaw
* Ex5, model totally misunderstood user's response: hallucinating user name as the recommender prof's name, and response with unrelated text

## P6

* Ex1 seems fine
* Ex2, model didn't respond as expected, but this scenario is a bit too edgy (or should be tuned with prompt, it's most likely not in our sim data)
* Ex3, temp 0 got the country residence wrong as OTHER
* Ex4, temp 0 did everything right but chose choice builder with a completely off question, temp 0.7 failed to generate formatted response
* Ex5, temp 0 emits additional value, but final output looks fine, temp 0.7 text response doesn't ask for next step

## P7

* Ex1, temp 0.7 got the field value wrong
* Ex2, model hallucinating lots of unrelated fields and values
* Ex3, this is a bad test example, the input itself is not correct
* Ex4 seems fine, temp 0 may need additional followup words in text response
* Ex5 model failed to detect has new data and invoke set fields

## P8

* Ex1, model failed invoke wants review and hallucinating the text response
* Ex2, model failed to point out what exactly are left
* Ex3, model failed to invoke wants review
* Ex4, model failed to recognize there is one field left
* Ex5, model gave the right answer to user question, but added additional confusing text response
* It looks like we need to have a deterministic tool to check the required field-value against what's filled, for guardrail the error like this (it seems to be hard for model to derive this info)

## P9

* Ex1 seems fine
* Ex2 model miss the wants save intent from user
* Ex3 seems fine
* Ex4 response seems fine, but i don't want to double check the contents, most likely have the same issues in P8
* Ex5 model extract info correctly, but use confusing words to respond

## P10

* We don't design anything around this now, no review on this section

## P11

* Same as P10

## P12

* Ex1 temp 0 just obey the requirement, temp 0.7 added the program selection choice. Both haiku are relevant to the theme though
* Ex2 model yield without checking fact, could solve this by giving the tool mentioned in P8
* Ex3 model can't catch the vibe and response in a proper way
* Ex4, i don't think this is a legit way to test prompt injection, ignore this
* Ex5, model didn't follow up with question about what "no" means
