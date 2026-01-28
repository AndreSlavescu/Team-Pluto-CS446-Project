# Pluto 

## Introduction

### What Are We Building?

We are building a mobile application that can automatically generate other mobile applications just from a simple prompt. Similar in nature to the compiler space, where research has positioned itself to build compilers that generate compilers, we believe building an applicaiton that leverages AI as a "compiler" to automatically compile mobile applications is the future direction for application development.

### Why Is What We're Building Interesting?

This project sits at the intersection of several hot topics:

- AI Agentic Systems
- Code synthesis driven by AI
- AI driven application design

By democratizing app creation, we enable users without programming expertise to bring their ideas to life just from a simple prompt; this enables a selection of more and more unique creations. The technical challenges are substantial; translating natural language requirements into functional, well-structured code requires a sophisticated agentic system that can manage a series of tools that a mobile application developer would typically have. Some examples of what this agent should be capable of are:

- Debugging React Native code with proper tools
- Validate that the code builds
- Test that the application is as expected from user spec / mock-ups

Addiionally, we implicitly explore the ever-growing topic of AI-assisted development; is it feasible at scale for untrained individuals? A thesis that is growing in complexity by nature of the accessibility of knowledge through smarter agentic LLM systems.

### Why Does This Project Make Sense In A Mobile Form?

A mobile form factor is ideal for this project for several reasons. First, the output of our application is mobile apps, so having the creation tool on the same platform provides a seamless experience for testing and iteration, for the respective creator. Second, mobile devices are abundant and relatively cheap, lowering the barrier to entry for potential app creators who may not have access to traditional development environments on more expensive hardware. Third, the constrained mobile interface encourages simplicity in the prompt-based interaction model, making the app generation process more intuitive for a wider range of users. Finally, users can capture inspiration on the fly and immediately begin prototyping their app ideas wherever they are, just by taking their phone out and typing a message.