import api from "./axios";



// =====================================================
// COMPANY DASHBOARD
// =====================================================


export const getCompanyDashboard = async()=>{

    return await api.get(
        "/company/dashboard/"
    );

};





// =====================================================
// COMPANY PROFILE
// =====================================================


export const getCompanyProfile = async()=>{

    return await api.get(
        "/company/profile/"
    );

};





export const updateCompanyProfile = async(data)=>{

    return await api.put(
        "/company/profile/",
        data
    );

};






export const uploadCompanyLogo = async(data)=>{


    return await api.post(

        "/company/profile/logo/",

        data,

        {

            headers:{

                "Content-Type":

                "multipart/form-data"

            }

        }

    );


};









// =====================================================
// COMPANY JOB MANAGEMENT
// =====================================================



// CREATE JOB

export const createCompanyJob = async(data)=>{

    return await api.post(
        "/company/jobs/create/",
        data
    );

};



// GET ALL COMPANY JOBS

export const getCompanyJobs = async()=>{

    return await api.get(
        "/company/jobs/"
    );

};



// UPDATE JOB

export const updateCompanyJob = async(
    id,
    data
)=>{

    return await api.put(
        `/company/jobs/${id}/update/`,
        data
    );

};



// DELETE JOB

export const deleteCompanyJob = async(id)=>{

    return await api.delete(
        `/company/jobs/${id}/delete/`
    );

};









// =====================================================
// COMPANY CANDIDATES
// =====================================================



export const getCompanyCandidates = async()=>{


    return await api.get(

        "/company/candidates/"

    );


};


export const searchCandidates = async(params={})=>{


    return await api.get(

        "/company/candidates/search/",

        { params }

    );


};







export const updateCandidateStatus = async(

    applicationId,

    data

)=>{


    return await api.patch(

        `/company/candidates/${applicationId}/status/`,

        data

    );


};



export const updateCandidateNotes = async(

    applicationId,

    recruiterNotes

)=>{


    return await api.patch(

        `/company/candidates/${applicationId}/notes/`,

        {
            recruiter_notes: recruiterNotes
        }

    );


};



export const notifyCandidateProfileViewed = async(applicationId)=>{

    try{

        return await api.post(

            `/company/candidates/${applicationId}/viewed/`

        );

    }

    catch(error){

        console.error(

            "NOTIFY PROFILE VIEWED ERROR:",

            error.response?.data || error.message

        );

    }

};




// =====================================================
// COMPANY INTERVIEWS
// =====================================================



export const getCompanyInterviews = async()=>{


    return await api.get(

        "/company/interviews/"

    );


};







export const createCompanyInterview = async(data)=>{


    return await api.post(

        "/company/interviews/create/",

        data

    );


};







export const updateInterviewStatus = async(

    interviewId,

    data

)=>{


    return await api.patch(

        `/company/interviews/${interviewId}/status/`,

        data

    );


};









// =====================================================
// COMPANY ANALYTICS
// =====================================================



export const getCompanyAnalytics = async()=>{


    return await api.get(

        "/company/analytics/"

    );


};









// =====================================================
// COMPANY SELECTION RESULTS
// =====================================================



export const getSelectionResults = async()=>{


    return await api.get(

        "/company/results/"

    );


};







export const updateCandidateResult = async(

    id,

    data

)=>{


    return await api.patch(

        `/company/results/${id}/`,

        data

    );


};









// =====================================================
// FORMAT DASHBOARD DATA
// =====================================================



export const formatCompanyStats=(data)=>{


    return {


        jobs:

        data.total_jobs || 0,



        applicants:

        data.total_applications || 0,



        shortlisted:

        data.shortlisted || 0,



        interviews:

        data.interviews || 0,



        selected:

        data.selected || 0


    };


};









// =====================================================
// DEFAULT EXPORT
// =====================================================



const companyApi={



    // Dashboard

    getCompanyDashboard,





    // Profile

    getCompanyProfile,

    updateCompanyProfile,

    uploadCompanyLogo,





    // Jobs

    createCompanyJob,

    getCompanyJobs,


    updateCompanyJob,

    deleteCompanyJob,





    // Candidates

    getCompanyCandidates,

    updateCandidateStatus,

    updateCandidateNotes,

    notifyCandidateProfileViewed,





    // Interviews

    getCompanyInterviews,

    createCompanyInterview,

    updateInterviewStatus,





    // Analytics

    getCompanyAnalytics,





    // Results

    getSelectionResults,

    updateCandidateResult,





    // Helper

    formatCompanyStats


};




export default companyApi;