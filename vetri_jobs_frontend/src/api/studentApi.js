// =====================================================
// STUDENT API
// Vetri Jobs Student Module
// =====================================================


import api from "./axios";





// =====================================================
// STUDENT DASHBOARD
// GET /api/student/dashboard/
// =====================================================


export const getStudentDashboard = async()=>{


    try{


        return await api.get(

            "/student/dashboard/"

        );


    }


    catch(error){


        console.error(

            "STUDENT DASHBOARD ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// STUDENT PROFILE
// GET /api/student/profile/
// =====================================================


export const getStudentProfile = async()=>{


    try{


        return await api.get(

            "/student/profile/"

        );


    }


    catch(error){


        console.error(

            "GET STUDENT PROFILE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE STUDENT PROFILE
// PUT /api/profile/update/
// =====================================================


export const updateStudentProfile = async(data)=>{


    try{


        return await api.put(

            "/student/profile/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE STUDENT PROFILE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPLOAD RESUME
// POST /api/student/profile/resume/
// =====================================================


export const uploadResume = async(file)=>{

    try{

        // Accept either a raw File (normal case) or a
        // FormData already built by the caller, so older
        // and newer call sites both keep working.

        let formData = file;


        if(!(file instanceof FormData)){

            formData = new FormData();

            formData.append(
                "resume",
                file
            );

        }


        return await api.post(

            "/student/resume/",

            formData,

            {
                headers:{
                    "Content-Type":
                    "multipart/form-data"
                }
            }

        );


    }
    catch(error){

        console.error(
            "RESUME UPLOAD ERROR:",
            error.response?.data ||
            error.message
        );

        throw error;

    }

};






// =====================================================
// JOB LIST
// GET /api/student/jobs/
// =====================================================


export const getJobs = async()=>{


    try{


        return await api.get(

            "/student/jobs/"

        );


    }


    catch(error){


        console.error(

            "GET JOBS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// SEARCH JOBS
// GET /api/student/jobs/search/
// =====================================================


export const searchJobs = async(keyword)=>{


    try{


        return await api.get(

            `/student/jobs/search/?search=${keyword}`

        );


    }


    catch(error){


        console.error(

            "JOB SEARCH ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET JOB DETAIL
// GET /api/student/jobs/:id/
// =====================================================


export const getJobDetails = async(jobId)=>{


    try{


        return await api.get(

            `/student/jobs/${jobId}/`

        );


    }


    catch(error){


        console.error(

            "JOB DETAIL ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// APPLY JOB
// POST /api/student/jobs/:id/apply/
// =====================================================


export const applyJob = async(jobId, payload)=>{


    try{


        return await api.post(

            `/student/jobs/${jobId}/apply/`,

            payload || {}

        );


    }


    catch(error){


        console.error(

            "JOB APPLICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// STUDENT APPLICATIONS
// GET /api/student/applications/
// =====================================================


export const getStudentApplications = async()=>{


    try{


        return await api.get(

            "/student/applications/"

        );


    }


    catch(error){


        console.error(

            "APPLICATIONS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// WITHDRAW APPLICATION
// DELETE /api/student/applications/:id/
// =====================================================


export const withdrawApplication = async(applicationId)=>{


    try{


        return await api.delete(

            `/student/applications/${applicationId}/`

        );


    }


    catch(error){


        console.error(

            "WITHDRAW APPLICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// STUDENT INTERVIEWS
// GET /api/student/interviews/
// =====================================================


export const getStudentInterviews = async()=>{


    try{


        return await api.get(

            "/student/interviews/"

        );


    }


    catch(error){


        console.error(

            "INTERVIEWS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// STUDENT NOTIFICATIONS
// GET /api/student/notifications/
// =====================================================


export const markNotificationRead = async(notificationId)=>{

    return await api.patch("/notifications/" + notificationId + "/read/");

};


export const deleteNotification = async(notificationId)=>{

    return await api.delete("/notifications/" + notificationId + "/delete/");

};


export const markAllNotificationsRead = async()=>{

    return await api.patch("/notifications/mark-all-read/");

};


export const getStudentNotifications = async()=>{


    try{


        return await api.get(

            "/student/notifications/"

        );


    }


    catch(error){


        console.error(

            "STUDENT NOTIFICATION ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// SAVE JOB
// POST /api/student/jobs/:id/save/
// =====================================================


export const saveJob = async(jobId)=>{


    try{


        return await api.post(

            `/student/jobs/${jobId}/save/`

        );


    }


    catch(error){


        console.error(

            "SAVE JOB ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// REMOVE SAVED JOB
// DELETE /api/student/jobs/:id/save/
// =====================================================


export const removeSavedJob = async(jobId)=>{


    try{


        return await api.delete(

            `/student/jobs/${jobId}/save/`

        );


    }


    catch(error){


        console.error(

            "REMOVE SAVED JOB ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// DASHBOARD DATA FORMATTER
// =====================================================


export const formatStudentStats=(data)=>{


    return {


        applied:

            data.total_applied
            ||
            0,



        shortlisted:

            data.shortlisted
            ||
            0,



        interviews:

            data.interviews
            ||
            0,



        selected:

            data.selected
            ||
            0,



        rejected:

            data.rejected
            ||
            0


    };


};


// =====================================================
// DELETE RESUME
// DELETE /api/student/profile/resume/:id/
// =====================================================


export const deleteResume = async(resumeId)=>{

    try{

        return await api.delete(

            `/student/resume/${resumeId}/`

        );

    }
    catch(error){

        console.error(
            "DELETE RESUME ERROR:",
            error.response?.data ||
            error.message
        );

        throw error;

    }

};

// =====================================================
// GET RESUME
// GET /api/student/profile/resume/
// =====================================================



export const getResume = async()=>{

    try{

        return await api.get(

            "/student/resume/"

        );

    }
    catch(error){

        console.error(
            "GET RESUME ERROR:",
            error.response?.data ||
            error.message
        );

        throw error;

    }

};

// =====================================================
// DOWNLOAD RESUME (forces an actual file download instead
// of opening in a new tab)
// GET /api/student/resume/:id/download/
// =====================================================
//
// The resume file itself lives on Cloudinary, and Cloudinary's
// direct URL (resume.resume_url) has no Content-Disposition
// header telling the browser to save it - so a plain <a href>
// link to it always just opens/previews the file in a new tab
// instead of downloading. The backend's dedicated /download/
// endpoint streams the file back with
// Content-Disposition: attachment, which forces a real download
// - but that endpoint requires the student's JWT auth header,
// which a plain HTML <a> tag has no way to send. So this fetches
// it through the authenticated `api` instance as a blob, then
// triggers the save using a temporary object URL - see
// triggerBlobDownload in ResumeManagement.jsx for the part that
// actually clicks a hidden link with the blob URL.

export const downloadResume = async(resumeId)=>{

    try{

        return await api.get(

            `/student/resume/${resumeId}/download/`,

            {
                responseType: "blob"
            }

        );

    }
    catch(error){

        console.error(
            "DOWNLOAD RESUME ERROR:",
            error.response?.data ||
            error.message
        );

        throw error;

    }

};

// =====================================================
// ELIGIBILITY CHECK
// =====================================================


export const checkEligibility = async(jobId)=>{


return await api.get(

`/student/jobs/${jobId}/eligibility/`

);


};

// =====================================================
// GET SAVED JOBS
// GET /api/student/saved-jobs/
// =====================================================


export const getSavedJobs = async()=>{


    try{


        return await api.get(

            "/student/saved-jobs/"

        );


    }


    catch(error){


        console.error(

            "GET SAVED JOBS ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};


// =====================================================
// FORMAT JOB DETAILS
// =====================================================

export const formatJobData=(job)=>{


    return {


        id: job.id,


        title:
        job.title || "",



        company:
        job.company_name ||
        job.company ||
        "",



        description:
        job.description || "",



        skills_required:
        job.skills_required || "",



        qualification_required:
        job.qualification_required || "",



        experience_required:
        job.experience_required || "",



        salary:
        job.salary || "Negotiable",



        location:
        job.location || "",



        job_type:
        job.job_type || "",



        work_mode:
        job.work_mode || "",



        vacancies:
        job.vacancies || 0,



        application_deadline:
        job.application_deadline || "",



        interview_process:
        job.interview_process || "",



        eligibility_criteria:
        job.eligibility_criteria || ""


    };


};


export const analyzeResume=(id)=>{


return api.post(

`/student/resume/${id}/analyse/`

);


};

export const getResumeVersions=()=>{


return api.get(

"/student/resume/versions/"

);


};








export default {


    getStudentDashboard,

    getStudentProfile,

    updateStudentProfile,

    uploadResume,

    getResume,

    deleteResume,

    downloadResume,

    getJobs,

    searchJobs,

    getJobDetails,

    applyJob,

    getStudentApplications,

    withdrawApplication,

    getStudentInterviews,

    getStudentNotifications,

    saveJob,

    removeSavedJob,

    formatStudentStats,

    checkEligibility,
    formatJobData,
    analyzeResume,


};
