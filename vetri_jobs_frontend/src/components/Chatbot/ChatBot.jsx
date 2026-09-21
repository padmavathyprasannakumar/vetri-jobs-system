import React, {

    useState,

    useRef,

    useEffect

} from "react";


import {

    useNavigate

} from "react-router-dom";


import {

    sendChatMessage

} from "../../api/chatbotApi";


import {

    getSiteBranding

} from "../../api/brandingApi";


import "./ChatBot.css";




function Chatbot(){



    const navigate = useNavigate();



    const [open,setOpen] = useState(false);


    const [chatbotAvatarUrl,setChatbotAvatarUrl] = useState(null);


    useEffect(()=>{

        getSiteBranding()

        .then(res=>setChatbotAvatarUrl(res.data?.chatbot_avatar_image_url || null))

        .catch(()=>{});

    },[]);



    const [message,setMessage] = useState("");



    const [attachedFile,setAttachedFile] = useState(null);



    const fileInputRef = useRef(null);


    const bodyRef = useRef(null);



    const [messages,setMessages] = useState([

        {

            sender:"bot",

            text:"Hello 👋 How can I help you today? You can also attach your resume and ask me to check it or make it ATS-friendly."

        }

    ]);



    const [loading,setLoading] = useState(false);



    // Window "slightly expands" once a real conversation has
    // started (more than the initial greeting) or while the
    // assistant is typing a reply - gives it room to breathe
    // instead of staying cramped at the tiny default size.

    const isExpanded = messages.length > 1 || loading;




    useEffect(()=>{

        if(bodyRef.current){

            bodyRef.current.scrollTop = bodyRef.current.scrollHeight;

        }

    },[messages,loading,open]);




    // ===============================
    // ATTACHMENT HANDLING
    // ===============================


    const handleAttachClick = ()=>{

        fileInputRef.current?.click();

    };


    const handleFileSelected = (e)=>{

        const file = e.target.files[0];

        if(!file) return;

        const allowed = [".pdf",".doc",".docx"];

        const isAllowed = allowed.some(ext=>

            file.name.toLowerCase().endsWith(ext)

        );

        if(!isAllowed){

            setMessages(prev=>[

                ...prev,

                {

                    sender:"bot",

                    text:"I can only accept PDF, DOC or DOCX files for resumes."

                }

            ]);

            e.target.value = "";

            return;

        }

        setAttachedFile(file);

        e.target.value = "";

    };


    const removeAttachment = ()=>{

        setAttachedFile(null);

    };




    const handleSend = async()=>{



        if(!message.trim() && !attachedFile)

            return;




        const userMessage = {


            sender:"user",

            text: message || (attachedFile ? "" : ""),

            attachment: attachedFile ? attachedFile.name : null


        };




        setMessages(prev=>[

            ...prev,

            userMessage

        ]);




        const pendingFile = attachedFile;

        const pendingMessage = message;


        setMessage("");

        setAttachedFile(null);


        setLoading(true);




        try{



            const response =

                await sendChatMessage(

                    pendingMessage,

                    pendingFile

                );




            const data = response.data || {};




            setMessages(prev=>[


                ...prev,


                {


                    sender:"bot",


                    text:

                    data.reply ||

                    "Sorry, I could not understand.",


                    // Present only when the bot ran a job-matching
                    // action (search_jobs / eligible_jobs) - lets
                    // real Apply/View cards render inline, agent-style,
                    // instead of just plain text.

                    matchedJobs: data.matched_jobs || null


                }


            ]);




            // Auto-navigate to the Jobs page when the bot's action
            // says to (currently only search_jobs/eligible_jobs set
            // this). The widget itself stays mounted/open across the
            // route change since it lives in the layout, not the page.

            if(data.navigate_to){

                navigate(data.navigate_to);

            }



        }

        catch(error){


            setMessages(prev=>[


                ...prev,


                {


                    sender:"bot",


                    text:

                    "Unable to connect with assistant."


                }


            ]);



        }

        finally{


            setLoading(false);


        }




    };




    const handleKeyPress=(e)=>{


        if(e.key==="Enter"){


            handleSend();


        }


    };




    return (



        <>



            {/* FLOATING BUTTON */}


            <button


            className="chatbot-button"


            onClick={()=>setOpen(!open)}


            >


                <i className={open ? "bi bi-x-lg" : (chatbotAvatarUrl ? "" : "bi bi-robot")}></i>

                {
                !open && chatbotAvatarUrl &&

                <img src={chatbotAvatarUrl} alt="AI" className="chatbot-button-avatar"/>
                }


                {
                !open &&

                <span className="chatbot-button-badge">AI</span>
                }


            </button>






            {


            open &&


            <div className={

                "chatbot-window" +

                (isExpanded ? " expanded" : "")

            }>




                <div className="chatbot-header">


                    <div className="chatbot-header-avatar">

                        {
                        chatbotAvatarUrl ?
                        <img src={chatbotAvatarUrl} alt="AI"/>
                        :
                        <i className="bi bi-robot"></i>
                        }

                    </div>


                    <div className="chatbot-header-text">

                        <h3>

                            Vetri AI Assistant

                        </h3>


                        <span>

                            <i className="chatbot-online-dot"></i>

                            Online

                        </span>

                    </div>




                    <button

                    className="chatbot-close-btn"


                    onClick={()=>setOpen(false)}


                    >

                        <i className="bi bi-x-lg"></i>

                    </button>


                </div>




                <div className="chatbot-body" ref={bodyRef}>


                    {


                    messages.map(

                        (item,index)=>(



                        <div


                        key={index}


                        className={

                        item.sender==="user"

                        ?

                        "chat-message user"

                        :

                        "chat-message bot"

                        }


                        >


                            {
                            item.attachment &&

                            <div className="chat-attachment-chip">

                                <i className="bi bi-file-earmark-text"></i>

                                {item.attachment}

                            </div>
                            }


                            {item.text}




                            {/* AGENT-STYLE JOB MATCH CARDS */}

                            {
                            item.matchedJobs && item.matchedJobs.length > 0 &&

                            <div className="chat-job-cards">

                                {
                                item.matchedJobs.map(job=>(

                                    <div className="chat-job-card" key={job.id}>


                                        <div className="chat-job-card-top">

                                            <strong>{job.title}</strong>

                                            {
                                            job.match_score !== null && job.match_score !== undefined &&

                                            <span className="chat-job-card-score">

                                                {job.match_score}% match

                                            </span>
                                            }

                                        </div>


                                        <p className="chat-job-card-sub">

                                            {job.company}
                                            {job.location ? ` \u2022 ${job.location}` : ""}

                                        </p>


                                        <div className="chat-job-card-actions">

                                            <a

                                            href={job.apply_url}

                                            className="chat-job-card-apply"

                                            onClick={(e)=>{

                                                e.preventDefault();

                                                navigate(job.apply_url);

                                            }}

                                            >

                                                Apply

                                            </a>


                                            <a

                                            href={job.details_url}

                                            className="chat-job-card-view"

                                            onClick={(e)=>{

                                                e.preventDefault();

                                                navigate(job.details_url);

                                            }}

                                            >

                                                View details

                                            </a>

                                        </div>


                                    </div>

                                ))
                                }

                            </div>
                            }


                        </div>


                        )

                    )


                    }




                    {


                    loading &&


                    <div className="chat-message bot typing-bubble">


                        <span className="typing-dot"></span>

                        <span className="typing-dot"></span>

                        <span className="typing-dot"></span>


                    </div>


                    }


                </div>




                {
                attachedFile &&

                <div className="chatbot-attachment-preview">

                    <i className="bi bi-file-earmark-text"></i>

                    <span>{attachedFile.name}</span>

                    <button onClick={removeAttachment}>✕</button>

                </div>
                }




                <div className="chatbot-input">


                    <input

                        type="file"

                        ref={fileInputRef}

                        style={{display:"none"}}

                        accept=".pdf,.doc,.docx"

                        onChange={handleFileSelected}

                    />


                    <button

                    type="button"

                    className="chatbot-attach-btn"

                    onClick={handleAttachClick}

                    title="Attach resume"

                    >

                        <i className="bi bi-paperclip"></i>

                    </button>


                    <input


                    value={message}


                    onChange={(e)=>

                        setMessage(

                            e.target.value

                        )

                    }


                    onKeyDown={handleKeyPress}


                    placeholder="Ask something..."


                    />






                    <button

                    className="chatbot-send-btn"


                    onClick={handleSend}


                    disabled={loading || (!message.trim() && !attachedFile)}


                    >

                        <i className="bi bi-send-fill"></i>

                    </button>


                </div>




            </div>



            }



        </>


    );


}



export default Chatbot;
