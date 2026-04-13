# LLM API Reference Implementation

This repository contains the LLM-facing components referenced in the article:

**"Architecting Intelligence: Confronting the Realities of Embedded AI"**

It has been shared to provide transparency into how the system was built and to support further exploration.

---

## Overview

This is a working reference implementation of an attempt to embed an LLM subsystem in to an existing fitness training application.

The code demonstrates:

- context management
- tool definition and dispatch
- multi-step LLM interaction (tool call → follow-up inference) but I did not handle sequential tool calls
- context summarization to manage token pressure (extremely simplistic)
- basic orchestration patterns required to make LLMs usable in an application

It was developed iteratively while exploring how LLMs actually behave when integrated into a real application.

The focus is on **behavior and architecture**, not framework design.  

None of the actual training application code is provided.

---

## Key Concepts Illustrated

If you are reading this alongside the article, the following concepts are directly reflected in the code:

- LLMs are stateless and require externally managed context
- Tool usage is inferred by the model but executed by the system
- Model output must be validated and controlled
- Context size directly impacts performance and correctness
- Additional system design is required to compensate for model limitations

---
