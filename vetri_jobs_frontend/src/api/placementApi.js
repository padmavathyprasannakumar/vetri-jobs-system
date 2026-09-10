// =====================================================
// PLACEMENT ADMIN API
// Vetri Jobs Placement Management
// =====================================================


import api from "./axios";




// =====================================================
// PLACEMENT DASHBOARD
// =====================================================

export const getPlacementDashboard = async()=>{


    try{


        return await api.get(

            "/placement/dashboard/"

        );


    }


    catch(error){


        console.error(

            "PLACEMENT DASHBOARD ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};








// =====================================================
// STUDENTS MANAGEMENT
// =====================================================


export const getPlacementStudents = async()=>{


    try{


        return await api.get(

            "/placement/students/"

        );


    }


    catch(error){


        console.error(

            "GET STUDENTS ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};







// =====================================================
// UPDATE STUDENT PLACEMENT STATUS
// PATCH /api/placement/students/:id/status/
// =====================================================


export const updateStudentPlacementStatus = async(

    studentId,

    data

)=>{


    try{


        return await api.patch(


            `/placement/students/${studentId}/status/`,


            data


        );


    }


    catch(error){


        console.error(

            "UPDATE STUDENT STATUS ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};







// =====================================================
// VERIFY STUDENT
// =====================================================


export const verifyStudent = async(

    id,

    data={}

)=>{

    try{


        return await api.patch(

            `/placement/students/${id}/verify/`,

            data

        );

    }


    catch(error){


        console.error(

            "VERIFY STUDENT ERROR:",

            error.response?.data || error.message

        );

        throw error;

    }


};




// =====================================================
// UPDATE STUDENT PROFILE (PLACEMENT ADMIN)
// =====================================================


export const updatePlacementStudent = async(

    id,

    data

)=>{

    try{


        return await api.patch(

            `/placement/students/${id}/`,

            data

        );

    }


    catch(error){


        console.error(

            "UPDATE STUDENT ERROR:",

            error.response?.data || error.message

        );

        throw error;

    }


};


export const createPlacementStudent = async(

    data

)=>{

    try{


        return await api.post(

            "/placement/students/create/",

            data

        );

    }


    catch(error){


        console.error(

            "CREATE STUDENT ERROR:",

            error.response?.data || error.message

        );


        throw error;

    }


};









// =====================================================
// COMPANIES MANAGEMENT
// =====================================================


export const getPlacementCompanies = async()=>{


    try{


        return await api.get(

            "/placement/companies/"

        );


    }


    catch(error){


        console.error(

            "GET COMPANIES ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};







export const getPlacementJobs = async()=>{

    return await api.get("/placement/jobs/");

};


export const updatePlacementJobStatus = async(jobId, status)=>{

    try{

        return await api.patch(

            `/placement/jobs/${jobId}/status/`,

            { status }

        );

    }

    catch(error){

        console.error(

            "UPDATE JOB STATUS ERROR:",

            error.response?.data || error.message

        );

        throw error;

    }

};


export const getCompanyHistory = async(companyId)=>{

    return await api.get("/placement/companies/" + companyId + "/history/");

};


export const createPlacementJob = async(jobData)=>{

    return await api.post("/company/jobs/create/", jobData);

};


export const createCompany = async(companyData)=>{

    return await api.post(

        "/placement/companies/",

        companyData

    );

};


export const verifyCompany = async(

    id,

    data={}

)=>{


    try{


        return await api.patch(

            `/placement/companies/${id}/verify/`,

            data

        );


    }


    catch(error){


        console.error(

            "VERIFY COMPANY ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};


// =====================================================
// UPDATE COMPANY STATUS
// PATCH /api/placement/companies/:id/status/
// =====================================================


export const updateCompanyStatus = async(

    companyId,

    data

)=>{


    try{


        return await api.patch(


            `/placement/companies/${companyId}/status/`,


            data


        );


    }


    catch(error){


        console.error(

            "UPDATE COMPANY STATUS ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};








// =====================================================
// PLACEMENT DRIVES
// =====================================================


export const getPlacementDrives = async()=>{


    return await api.get(

        "/placement/drives/"

    );


};






export const createPlacementDrive = async(data)=>{


    return await api.post(

        "/placement/drives/",

        data

    );


};







export const updatePlacementDrive = async(

    id,

    data

)=>{


    return await api.put(

        `/placement/drives/${id}/`,

        data

    );


};







export const deletePlacementDrive = async(id)=>{


    return await api.delete(

        `/placement/drives/${id}/`

    );


};









// =====================================================
// REPORTS
// =====================================================


export const getPlacementReports = async()=>{


    return await api.get(

        "/placement/reports/"

    );


};




export const scheduleAutomatedReport = async(data)=>{


    return await api.post(

        "/placement/reports/schedule/",

        data

    );


};









// =====================================================
// NOTIFICATIONS
// =====================================================


export const sendPlacementNotification = async(data)=>{


    return await api.post(

        "/notifications/send/",

        data

    );


};

// =====================================================
// UPDATE DRIVE STATUS
// PATCH /api/placement/drives/:id/status/
// =====================================================


export const updateDriveStatus = async(

    driveId,

    data

)=>{


    try{


        return await api.patch(

            `/placement/drives/${driveId}/status/`,

            data

        );


    }


    catch(error){


        console.error(

            "UPDATE DRIVE STATUS ERROR:",

            error.response?.data || error.message

        );


        throw error;


    }


};







// =====================================================
// DEFAULT EXPORT
// =====================================================




// =====================================================
// CANDIDATE PIPELINE
// =====================================================


export const getCandidatePipeline = async()=>{

    return await api.get(

        "/placement/candidates/pipeline/"

    );

};



export const updatePlacementApplicationStatus = async(

    applicationId,

    data

)=>{

    return await api.patch(

        `/placement/application/${applicationId}/status/`,

        data

    );

};


const placementApi = {


    
    // Dashboard

    getPlacementDashboard,



    // Students

    getPlacementStudents,

    updateStudentPlacementStatus,

    verifyStudent,
    updatePlacementStudent,



    // Companies

    getPlacementCompanies,

    updateCompanyStatus,

    verifyCompany,



    // Drives

    getPlacementDrives,

    createPlacementDrive,

    updatePlacementDrive,
    updateDriveStatus,

    deletePlacementDrive,



    // Reports

    getPlacementReports,



    // Notifications

    sendPlacementNotification,



    // Candidate Pipeline

    getCandidatePipeline,

    updatePlacementApplicationStatus



};



export default placementApi;