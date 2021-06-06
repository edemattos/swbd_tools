swbd_tools
==========

Tools for processing Switchboard for dependency parsing and disfluency processing research

This is a disorganised code dump.

convert.py is the main script.

Many of the other utilities are disused. I'll clean this up at some point.

Converting Switchboard NXT to Universal Dependencies v2
=======================================================

`nxt_convert.py` has been updated so that it outputs CoNLL-U v2 trees instead of CoNLL-X. 
Ensure the [Java command](https://github.com/UniversalDependencies/docs/issues/717#issuecomment-664586450) points to 
Stanford CoreNLP v4.0.0 or later by modifying the classpath `-cp` if necessary.
