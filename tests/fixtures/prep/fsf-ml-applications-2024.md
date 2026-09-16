# FSF is working on freedom in machine learning applications

In the document, the section titled "# FSF is working on freedom in machine learning applications" is a focused exploration of the Free Software Foundation's (FSF) initiative to ensure software freedom in the context of machine learning applications. This section is nestled within the broader discussion on the intersection of technology and user rights, highlighting the FSF's proactive approach to addressing the unique challenges posed by ML. It details the formation of a dedicated working group, comprising FSF's board members, staff, and management, who are collaborating to establish a comprehensive set of criteria. These criteria aim to ascertain the degree to which ML applications uphold the principles of software freedom, a testament to the FSF's commitment to safeguarding user rights in the rapidly evolving digital landscape.


Machine learning (ML) applications raise the issue of whether they respect users' software freedom. The Free Software Foundation (FSF) is preparing a statement of criteria to determine when a machine learning application is free (as in freedom). The statement is being prepared by a working group consisting of FSF's board members, staff, and management, and they have consulted various external experts.




Q: What is the Free Software Foundation's (FSF) initiative regarding software freedom in machine learning applications?
Q: How is the FSF addressing the unique challenges posed by machine learning in the context of user rights?
Q: What does the section reveal about the FSF's proactive approach to ensuring freedom in machine learning applications?



Summary: The section discusses the Free Software Foundation's (FSF) efforts to safeguard software freedom in machine learning applications, emphasizing their proactive approach to addressing the unique challenges posed by ML.

Keywords: Free Software Foundation, machine learning applications, software freedom, unique challenges, proactive approach, working group.

### Freedom challenges in ML beyond software

In this section, we delve into the intricacies of freedom challenges in machine learning (ML) that extend beyond the realm of software. While ML applications are fundamentally a blend of software and data, this section specifically focuses on the latter - the model parameters. These parameters, encompassing the model weights in neural network-based applications, serve as both the output of the training process and the input that shapes the system's behavior. By exploring these aspects, we aim to shed light on the unique freedom challenges they present, distinct from those encountered in traditional software development.


Machine learning applications are only partially software. Each one includes software, plus data that is the result of training. Such data can be referred to generally as "model parameters." In the case of neural network based applications, these are known as the model weights. Model parameters are both outputs of and inputs of the software of a machine learning system, and they influence or control the system's responses.

Model parameters are made by running training software over training data, but they are not necessarily the result of translating anything written by a human author. So, training data is not the "source code" of model parameters in the usual sense. The model parameters are not comprehensible as such by humans, so it is not practical to study or adapt an ML application by analyzing or editing model parameters directly. Also, the computation of model parameters often requires processing large numbers of examples gathered in the training data. The influence of any one example on the control data thus generated can be subtle and indirect. So, in practice, studying and adapting an ML application is usually done, for example, by running it over different sets of prompt data, analyzing training data, and incrementally training or retraining the model from scratch.

The FSF's conclusion is focused mainly on what must be distributed to users of an ML application so that they are able to control their own computing. Such an ML application could be called a free (or libre) machine learning application.




Q: What are the freedom challenges in machine learning that go beyond software?
Q: How do model parameters in machine learning, specifically model weights in neural networks, present freedom challenges?
Q: What role do model parameters play in shaping the behavior of machine learning systems?



Summary: This section explores the freedom challenges in machine learning (ML) that go beyond software, focusing on model parameters, such as the weights in neural networks, which are crucial for shaping system behavior and are the output of the training process.

Keywords: machine learning, freedom challenges, model parameters, neural networks, weights, system behavior, training process.

### Close to a conclusion

In the final stages of our discourse on the Free Software Foundation's (FSF) role, this section marks the culmination of intense efforts initiated in May of the current year. The working group has successfully concluded their deliberations and is now engaged in the meticulous task of formulating the precise language that will encapsulate the definition of a free machine learning application. This definition will ensure that all software components within a free ML application uphold the four essential freedoms that characterize free software, as outlined by the FSF.


After several conversations about the responsibility of the FSF in this discussion, serious work to come to a unanimous conclusion started in May of this year. That work has now concluded, and the working group is currently working to draft the exact text that will form the definition of a free machine learning application.

All software included in a free ML application has to offer every user 
[the four freedoms that define free software](https://www.gnu.org/philosophy/free-sw.html). This applies to both 
the software that processes training data, and the software that 
interprets model parameters as context for prompts to produce 
human-usable output. This is necessary but not sufficient. 
Additionally, given our current understanding of ML applications, we 
believe that we cannot say a ML application is free unless all its 
training data and the related scripts for processing it respect all 
users, following the four freedoms. In addition, granting users the 
four freedoms may translate into a demand that the ML application's 
release includes the model parameters that represent its training, and 
that users are permitted to use and redistribute the parameters and 
modified versions of them.

ML applications that do not offer the four freedoms to all users are, by definition, nonfree, even if their software components are free.




Q: What is the current status of the working group's efforts regarding the Free Software Foundation's role?
Q: When did the working group initiate their deliberations on the Free Software Foundation's role?
Q: What is the next step for the working group after concluding their deliberations?



Summary: The working group has completed their discussions and is now refining the language to define a free machine learning application, ensuring all components adhere to the four essential freedoms.

Keywords: Free Software Foundation, working group, final stages, definition, free machine learning application, four essential freedoms, language formulation.

### Freedom may not equal justice

In this document, the section titled "Freedom may not equal justice" delves into the ethical implications of nonfree software, particularly in the context of machine learning applications. Following a discussion on the Free Software Foundation's stance against nonfree software due to its denial of user control, this section explores the nuanced question of whether all nonfree ML applications are ethically unjust. It acknowledges potential valid reasons for nonfree ML applications, such as the protection of sensitive data like personal medical information. However, it also raises the possibility that using such applications could be ethically justifiable if they significantly aid in performing critical tasks.


FSF considers all nonfree software to be unjust to its users because it denies them the freedom to control their own computing. A further question is whether all nonfree ML applications are ethically unjust. It may be that some nonfree ML have valid moral reasons for not releasing training data, such as personal medical data. In that case, we would describe the application as a whole as nonfree. But using it could be ethically excusable if it helps you do a specialized job that is vital for society, such as diagnosing disease or injury. For the FSF to consider usage of such a nonfree ML application to be just, its component software must be free, and the ML application as a whole would have to be distributed to users in a form and manner that reasonably and flexibly supports incremental training, or retraining differently from scratch, or both.

FSF will continue to deepen the discussion on these topics during the 
drafting process. If you are interested in sharing your thoughts, 
please email, associate members can join the FSF [member forum](https://forum.members.fsf.org/). To 
further support this work, join the FSF or [donate](https://fsf.org/donate).




Q: What ethical implications does the document discuss regarding nonfree software in machine learning applications?
Q: Does the document argue that all nonfree machine learning applications are ethically unjust?
Q: What potential valid reasons for nonfree machine learning applications does the document acknowledge?



Summary: The section "Freedom may not equal justice" examines the ethical dilemma of nonfree software in machine learning, questioning if all nonfree ML applications are inherently unjust, despite the Free Software Foundation's opposition to nonfree software for its lack of user control.

Keywords: nonfree software, machine learning, Free Software Foundation, user control, ethical dilemma, justice, freedom, ethical implications.

### About the Free Software Foundation

In this document, the section titled "About the Free Software Foundation" is a dedicated subsection that delves into the history, mission, and evolution of the Free Software Foundation (FSF). It provides a concise overview of the organization's establishment in 1985 and its primary objective to advocate for and safeguard users' rights in using, studying, copying, modifying, and redistributing computer software. The section also hints at the FSF's adaptability in addressing emerging challenges, such as the recent surge in machine learning applications, and its commitment to exploring the ethical implications of these advancements.


The FSF was founded in 1985 to promote and protect computer users' right to use, study, copy, modify, and redistribute computer programs. Over the years it has addressed new challenges, resulting for example in releasing new versions of FSF's GNU family of licenses. The current rapid development and public interest in machine learning applications is another opportunity for the FSF to explore a moral and ethical question, clarifying what it takes for users to be able to control their own computing when using these applications.

Donations to support the FSF's work can be made at [https://donate.fsf.org](https://donate.fsf.org/).

More information about the FSF, as well as important information for 
journalists and publishers, is at [https://www.fsf.org/press](https://www.fsf.org/press).




Q: When was the Free Software Foundation established?
Q: What is the primary mission of the Free Software Foundation?
Q: How does the Free Software Foundation address emerging challenges?



Summary: The "About the Free Software Foundation" section offers a historical and mission-focused perspective on the Free Software Foundation (FSF), highlighting its founding in 1985 and its commitment to protecting users' rights in software usage, study, copying, modification, and redistribution. It also touches upon the FSF's adaptability in tackling new challenges.

Keywords: Free Software Foundation, 1985, users' rights, software usage, study, copying, modification, redistribution, adaptability, challenges.

### Media Contacts

In the "Media Contacts" section of our document, we provide essential contact information for our organization's key representatives. This section is designed to facilitate communication with the Free Software Foundation (FSF) and its leadership. Here, you'll find the details of Zoë Kooyman, our Executive Director, including her email address and phone number. This information is crucial for journalists, researchers, or anyone seeking to connect with FSF for interviews, collaborations, or inquiries related to our mission and activities.


Zoë Kooyman

Executive Director

[zoe@fsf.org](mailto:zoe@fsf.org)

+1 (617) 542-5942

- An artistic rendering designed to visualize and illustrate the abstract structure of cyberspace through a zero-and-one texture and model.© 2022 PantheraLeo1359531. This image is licensed under a Creative Commons CC0 1.0 Universal Public Domain Dedication.*

Q: Who is the Executive Director of the Free Software Foundation (FSF) listed in the Media Contacts section?

Q: What contact information is provided for Zoë Kooyman, the Executive Director of the Free Software Foundation (FSF), in the Media Contacts section?

Q: Why is the Media Contacts section important for journalists, researchers, or anyone seeking to connect with the Free Software Foundation (FSF)?


Summary: The "Media Contacts" section offers vital contact details for the Free Software Foundation's (FSF) key representatives, primarily focusing on Zoë Kooyman, the Executive Director, to enable seamless communication for interviews, collaborations, or inquiries.

Keywords: Free Software Foundation, Media Contacts, Zoë Kooyman, Executive Director, email address, phone number, journalists, researchers, interviews, collaborations, inquiries.
