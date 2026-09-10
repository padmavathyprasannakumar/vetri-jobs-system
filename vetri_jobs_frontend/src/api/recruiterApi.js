// =====================================================
// RECRUITER API
// Vetri Jobs Recruiter Module
//
// Role:
// company / recruiter
//
// Features:
// - Company profile
// - Job requirements
// - Candidate management
// - Resume review
// - Interview scheduling
// - Selection results
// =====================================================


import api from "./axios";





// =====================================================
// RECRUITER DASHBOARD
// GET /api/company/dashboard/
// =====================================================


export const getRecruiterDashboard = async()=>{


    try{


        return await api.get(

            "/company/dashboard/"

        );


    }


    catch(error){


        console.error(

            "RECRUITER DASHBOARD ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET RECRUITER PROFILE
// GET /api/company/profile/
// =====================================================


export const getRecruiterProfile = async()=>{


    try{


        return await api.get(

            "/company/profile/"

        );


    }


    catch(error){


        console.error(

            "RECRUITER PROFILE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE RECRUITER / COMPANY PROFILE
// PUT /api/company/profile/
// =====================================================


export const updateRecruiterProfile = async(data)=>{


    try{


        return await api.put(

            "/company/profile/",

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE RECRUITER PROFILE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// CREATE JOB REQUIREMENT
// POST /api/company/jobs/create/
// =====================================================


export const createRecruitmentJob = async(data)=>{


    try{


        return await api.post(

            "/company/jobs/create/",

            data

        );


    }


    catch(error){


        console.error(

            "CREATE RECRUITMENT JOB ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET RECRUITER JOBS
// GET /api/company/jobs/
// =====================================================


export const getRecruiterJobs = async()=>{


    try{


        return await api.get(

            "/company/jobs/"

        );


    }


    catch(error){


        console.error(

            "RECRUITER JOB LIST ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// GET JOB DETAILS
// GET /api/company/jobs/:id/
// =====================================================


export const getRecruiterJobDetails = async(jobId)=>{


    try{


        return await api.get(

            `/company/jobs/${jobId}/`

        );


    }


    catch(error){


        console.error(

            "RECRUITER JOB DETAIL ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE JOB REQUIREMENT
// PUT /api/company/jobs/:id/
// =====================================================


export const updateRecruitmentJob = async(jobId,data)=>{


    try{


        return await api.put(

            `/company/jobs/${jobId}/`,

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE JOB ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// DELETE JOB REQUIREMENT
// DELETE /api/company/jobs/:id/
// =====================================================


export const deleteRecruitmentJob = async(jobId)=>{


    try{


        return await api.delete(

            `/company/jobs/${jobId}/`

        );


    }


    catch(error){


        console.error(

            "DELETE JOB ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// VIEW ELIGIBLE CANDIDATES
// GET /api/company/candidates/
// =====================================================


export const getEligibleCandidates = async()=>{


    try{


        return await api.get(

            "/company/candidates/"

        );


    }


    catch(error){


        console.error(

            "ELIGIBLE CANDIDATES ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// REVIEW RESUME
// GET RESUME DATA
// =====================================================


export const reviewCandidateResume = async(applicationId)=>{


    try{


        return await api.get(

            `/company/candidates/${applicationId}/`

        );


    }


    catch(error){


        console.error(

            "RESUME REVIEW ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// SHORTLIST CANDIDATE
// PATCH /api/company/candidates/:id/status/
// =====================================================


export const shortlistCandidate = async(applicationId)=>{


    try{


        return await api.patch(


            `/company/candidates/${applicationId}/status/`,


            {

                status:"shortlisted"

            }


        );


    }


    catch(error){


        console.error(

            "SHORTLIST ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// REJECT CANDIDATE
// =====================================================


export const rejectCandidate = async(applicationId)=>{


    try{


        return await api.patch(


            `/company/candidates/${applicationId}/status/`,


            {

                status:"rejected"

            }


        );


    }


    catch(error){


        console.error(

            "REJECT CANDIDATE ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// UPDATE SELECTION RESULT
// =====================================================


export const updateSelectionResult = async(

applicationId,

result

)=>{


    try{


        return await api.patch(


            `/company/candidates/${applicationId}/status/`,


            {

                status:result

            }


        );


    }


    catch(error){


        console.error(

            "SELECTION RESULT ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// SCHEDULE INTERVIEW
// POST /api/company/interviews/create/
// =====================================================


export const scheduleInterview = async(data)=>{


    try{


        return await api.post(

            "/company/interviews/create/",

            data

        );


    }


    catch(error){


        console.error(

            "SCHEDULE INTERVIEW ERROR:",

            error.response?.data
            ||
            error.message

        );


        throw error;


    }


};








// =====================================================
// RECRUITER STATISTICS FORMATTER
// =====================================================


export const formatRecruiterStats=(data)=>{


    return {


        activeJobs:

            data.active_jobs || 0,


        totalApplicants:

            data.total_applicants || 0,


        shortlisted:

            data.shortlisted || 0,


        interviews:

            data.interviews || 0,


        selected:

            data.selected || 0


    };


};








export default {


    getRecruiterDashboard,

    getRecruiterProfile,

    updateRecruiterProfile,

    createRecruitmentJob,

    getRecruiterJobs,

    getRecruiterJobDetails,

    updateRecruitmentJob,

    deleteRecruitmentJob,

    getEligibleCandidates,

    reviewCandidateResume,

    shortlistCandidate,

    rejectCandidate,

    updateSelectionResult,

    scheduleInterview,

    formatRecruiterStats


};