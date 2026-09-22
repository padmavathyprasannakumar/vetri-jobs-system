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

    downloadResume

} from "../../api/studentApi";


import {

    getSiteBranding

} from "../../api/brandingApi";


import {

    useAuth

} from "../../context/AuthContext";


import "./ChatBot.css";




// =================================
// Role-aware greeting - the old single hardcoded message
// ("...attach your resume...") made no sense for a company
// recruiter, who has no resume of their own to attach.
// =================================

const getGreeting = (role)=>{

    if(role==="company"){

        return "Hello 👋 How can I help you today? Ask me to find candidates, check applicants for a job, or see your upcoming interviews.";

    }

    if(role==="student"){

        return "Hello 👋 How can I help you today? You can also attach your resume and ask me to check it or make it ATS-friendly, or ask for a mock interview.";

    }

    return "Hello 👋 How can I help you today?";

};




function Chatbot(){



    const navigate = useNavigate();



    const { user } = useAuth();



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

            text: getGreeting(user?.role)

        }

    ]);


    useEffect(()=>{

        setMessages(prev=>

            prev.length===1 && prev[0].sender==="bot"

            ? [{ sender:"bot", text: getGreeting(user?.role) }]

            : prev

        );

    // eslint-disable-next-line react-hooks/exhaustive-deps
    },[user?.role]);



    const [loading,setLoading] = useState(false);


    const [downloadingIndex,setDownloadingIndex] = useState(null);



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




    // ===============================
    // IN-CHAT RESUME DOWNLOAD
    // ===============================


    const handleDownloadResume = async(resumeId, filename, index)=>{

        setDownloadingIndex(index);

        try{

            const response = await downloadResume(resumeId);

            const blobUrl = window.URL.createObjectURL(

                new Blob([response.data])

            );

            const link = document.createElement("a");

            link.href = blobUrl;

            link.download = filename || "resume";

            document.body.appendChild(link);

            link.click();

            link.remove();

            window.URL.revokeObjectURL(blobUrl);

        }

        catch(error){

            setMessages(prev=>[

                ...prev,

                {

                    sender:"bot",

                    text:"Sorry, I couldn't download that file just now. Try again from the Resume page."

                }

            ]);

        }

        finally{

            setDownloadingIndex(null);

        }

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


                    matchedJobs: data.matched_jobs || null,


                    candidates: data.candidates || null,


                    resumeDownload: data.resume_download || null,


                    notifications: data.notifications || null,


                    // Present only right after a mock interview
                    // session concludes - renders a scored report
                    // card (overall/communication/technical scores,
                    // strengths, areas to improve) instead of
                    // leaving the score buried in plain text.

                    mockInterviewReport: data.mock_interview_report || null


                }


            ]);




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




                            {/* AGENT-STYLE JOB MATCH CARDS (student) */}

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

                                            {
                                            job.already_applied ?

                                            <span className="chat-job-card-applied-badge">

                                                ✓ Already Applied

                                            </span>

                                            :

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
                                            }


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




                            {/* AGENT-STYLE CANDIDATE CARDS (company) */}

                            {
                            item.candidates && item.candidates.length > 0 &&

                            <div className="chat-job-cards">

                                {
                                item.candidates.map((c,idx)=>(

                                    <div className="chat-job-card" key={idx}>


                                        <div className="chat-job-card-top">

                                            <strong>{c.name}</strong>

                                            {
                                            c.match_score !== null && c.match_score !== undefined &&

                                            <span className="chat-job-card-score">

                                                {c.match_score}% match

                                            </span>
                                            }

                                        </div>


                                        <p className="chat-job-card-sub">

                                            {c.course || c.department || ""}
                                            {c.cgpa ? ` \u2022 CGPA ${c.cgpa}` : ""}
                                            {c.status ? ` \u2022 ${c.status}` : ""}

                                        </p>


                                        <div className="chat-job-card-actions">

                                            <a

                                            href="/company/candidates"

                                            className="chat-job-card-view"

                                            onClick={(e)=>{

                                                e.preventDefault();

                                                navigate("/company/candidates");

                                            }}

                                            >

                                                View in Candidates

                                            </a>

                                        </div>


                                    </div>

                                ))
                                }

                            </div>
                            }




                            {/* IN-CHAT RESUME DOWNLOAD BUTTON */}

                            {
                            item.resumeDownload &&

                            <div className="chat-job-cards">

                                <div className="chat-job-card">

                                    <div className="chat-job-card-top">

                                        <strong>{item.resumeDownload.filename}</strong>

                                    </div>

                                    <div className="chat-job-card-actions">

                                        <button

                                        type="button"

                                        className="chat-job-card-apply"

                                        disabled={downloadingIndex===index}

                                        onClick={()=>handleDownloadResume(

                                            item.resumeDownload.resume_id,

                                            item.resumeDownload.filename,

                                            index

                                        )}

                                        >

                                            {
                                            downloadingIndex===index

                                            ? "Downloading..."

                                            : "Download"
                                            }

                                        </button>

                                    </div>

                                </div>

                            </div>
                            }




                            {/* NOTIFICATIONS LIST */}

                            {
                            item.notifications && item.notifications.length > 0 &&

                            <div className="chat-notification-list">

                                {
                                item.notifications.map((n,idx)=>(

                                    <div

                                    className={

                                        "chat-notification-item" +

                                        (n.is_read ? "" : " unread")

                                    }

                                    key={idx}

                                    >

                                        {
                                        n.title &&

                                        <strong>{n.title}</strong>
                                        }

                                        <p>{n.message}</p>

                                    </div>

                                ))
                                }

                            </div>
                            }




                            {/* MOCK INTERVIEW SCORE REPORT */}

                            {
                            item.mockInterviewReport &&

                            <div className="chat-interview-report">

                                {
                                item.mockInterviewReport.overall_score !== null &&
                                item.mockInterviewReport.overall_score !== undefined &&

                                <div className="chat-interview-report-scores">

                                    <div className="chat-interview-report-score-box overall">

                                        <span className="chat-interview-report-score-value">

                                            {item.mockInterviewReport.overall_score}

                                        </span>

                                        <span className="chat-interview-report-score-label">

                                            Overall

                                        </span>

                                    </div>


                                    <div className="chat-interview-report-score-box">

                                        <span className="chat-interview-report-score-value">

                                            {item.mockInterviewReport.communication_score ?? "-"}

                                        </span>

                                        <span className="chat-interview-report-score-label">

                                            Communication

                                        </span>

                                    </div>


                                    <div className="chat-interview-report-score-box">

                                        <span className="chat-interview-report-score-value">

                                            {item.mockInterviewReport.technical_score ?? "-"}

                                        </span>

                                        <span className="chat-interview-report-score-label">

                                            Technical

                                        </span>

                                    </div>

                                </div>
                                }


                                {
                                item.mockInterviewReport.strengths?.length > 0 &&

                                <div className="chat-interview-report-section">

                                    <strong>Strengths</strong>

                                    <ul>

                                        {
                                        item.mockInterviewReport.strengths.map((s,i)=>(

                                            <li key={i}>{s}</li>

                                        ))
                                        }

                                    </ul>

                                </div>
                                }


                                {
                                item.mockInterviewReport.areas_to_improve?.length > 0 &&

                                <div className="chat-interview-report-section">

                                    <strong>Areas to improve</strong>

                                    <ul>

                                        {
                                        item.mockInterviewReport.areas_to_improve.map((a,i)=>(

                                            <li key={i}>{a}</li>

                                        ))
                                        }

                                    </ul>

                                </div>
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
