import React from "react";


import {

    BrowserRouter,

    Routes,

    Route,

    Navigate

} from "react-router-dom";




// =====================================================
// LAYOUTS
// =====================================================


import MainLayout from "./layouts/MainLayout/MainLayout";

import StudentLayout from "./layouts/StudentLayout/StudentLayout";

import CompanyLayout from "./layouts/CompanyLayout/CompanyLayout";

import PlacementLayout from "./layouts/PlacementLayout/PlacementLayout";





// =====================================================
// ROUTE GUARDS
// =====================================================


import ProtectedRoute from "./routes/ProtectedRoute";







// =====================================================
// PUBLIC PAGES
// =====================================================


import Home from "./pages/public/Home/Home";





import CompanyRegister
from "./pages/public/Register/CompanyRegister";









// =====================================================
// STUDENT
// =====================================================


import StudentDashboard
from "./pages/student/Dashboard/StudentDashboard";


import StudentProfile
from "./pages/student/Profile/StudentProfile";


import Jobs
from "./pages/student/Jobs/Jobs";


import AIAssistant
from "./pages/student/AIAssistant/AIAssistant";


import Applications
from "./pages/student/Applications/Applications";


import Interviews
from "./pages/student/Interviews/Interviews";


import ResumeManagement
from "./pages/student/Resume/ResumeManagement";

import JobDetails 
from "./pages/student/Jobs/JobDetails";


import EligibilityCheck 
from "./pages/student/Jobs/EligibilityCheck";


import ApplyJob 
from "./pages/student/Jobs/ApplyJob";

import Notifications
from "./pages/student/Notifications/Notifications";

import SavedJobs
from "./pages/student/SavedJobs/SavedJobs";








// =====================================================
// COMPANY
// =====================================================


import CompanyDashboard 
from "./pages/company/Dashboard/CompanyDashboard";


import CompanyProfile 
from "./pages/company/Profile/CompanyProfile";


import ManageJobs 
from "./pages/company/Jobs/ManageJobs";

import CreateJob
from "./pages/company/Jobs/CreateJob";


import Candidates 
from "./pages/company/Candidates/Candidates";



import CompanyAIAssistant
from "./pages/company/AIAssistant/CompanyAIAssistant";


import CompanyNotifications
from "./pages/company/Notifications/CompanyNotifications";


import Interview 
from "./pages/company/Interviews/Interview";


import CompanyAnalytics
from "./pages/company/Analytics/CompanyAnalytics";


import SelectionResults
from "./pages/company/Results/SelectionResults";





// =====================================================
// PLACEMENT ADMIN
// =====================================================


import PlacementDashboard
from "./pages/placement/Dashboard/PlacementDashboard";


import Students
from "./pages/placement/Students/Students";


import AddEditStudent
from "./pages/placement/Students/AddEditStudent";


import Companies
from "./pages/placement/Companies/Companies";


import Drives
from "./pages/placement/Drives/Drives";


import PlacementInterviews
from "./pages/placement/Interviews/Interviews";


import CandidatePipeline
from "./pages/placement/CandidatePipeline/CandidatePipeline";


import PlacementChatbot
from "./pages/placement/Chatbot/PlacementChatbot";


import JobListings
from "./pages/placement/JobListings/JobListings";


import ManageResumes
from "./pages/placement/ManageResumes/ManageResumes";


import SendNotifications
from "./pages/placement/SendNotifications/SendNotifications";


import Reports
from "./pages/placement/Reports/Reports";









// =====================================================
// COMPONENTS
// =====================================================


import Chatbot from "./components/Chatbot/ChatBot";

import NotFound from "./pages/public/NotFound/NotFound";






// =====================================================
// UNAUTHORIZED PAGE
// =====================================================


const Unauthorized=()=>{


return (

<div className="text-center mt-5">


<h1>

403

</h1>


<h3>

Access Denied

</h3>


<p>

You don't have permission to view this page.

</p>


</div>

);


};










function App(){



return (

<BrowserRouter>


<Routes>





{/* =====================================================
                    PUBLIC ROUTES
===================================================== */}



<Route element={<MainLayout/>}>


<Route

path="/"

element={<Home/>}

/>




<Route

path="/student/login"

element={<Navigate to="/" replace/>}

/>



{/*
    Student self-registration has been removed - student
    accounts are now created only by a placement admin
    (via Django Admin or the Placement > Students > Add
    Student page). Any old bookmarked/shared link to
    /student/register now just lands on the home page's
    login card, same as the retired /student/login route
    above, instead of 404ing.
*/}

<Route

path="/student/register"

element={<Navigate to="/" replace/>}

/>




<Route

path="/company/login"

element={<Navigate to="/" replace/>}

/>



<Route

path="/placement/login"

element={<Navigate to="/" replace/>}

/>



<Route

path="/company/register"

element={<CompanyRegister/>}

/>






<Route

path="/unauthorized"

element={<Unauthorized/>}

/>



</Route>












{/* =====================================================
                    STUDENT
===================================================== */}



<Route

path="/student"

element={

<ProtectedRoute

allowedRoles={[

"student"

]}

/>

}

>


<Route element={<StudentLayout/>}>


<Route

path="dashboard"

element={<StudentDashboard/>}

/>


<Route

path="profile"

element={<StudentProfile/>}

/>


<Route

path="jobs"

element={<Jobs/>}

/>


<Route

path="ai-assistant"

element={<AIAssistant/>}

/>


<Route

path="applications"

element={<Applications/>}

/>


<Route

path="interviews"

element={<Interviews/>}

/>


<Route

path="resume"

element={<ResumeManagement/>}

/>

<Route

path="jobs/:id"

element={<JobDetails/>}

/>



<Route

path="jobs/:id/eligibility"

element={<EligibilityCheck/>}

/>



<Route

path="jobs/:id/apply"

element={<ApplyJob/>}

/>

<Route

path="notifications"

element={<Notifications/>}

/>

<Route

path="saved-jobs"

element={<SavedJobs/>}

/>


</Route>


</Route>












{/* =====================================================
                    COMPANY
===================================================== */}



<Route

path="/company"

element={

<ProtectedRoute

allowedRoles={[

"company"

]}

/>

}

>


<Route element={<CompanyLayout/>}>


<Route

path="dashboard"

element={<CompanyDashboard/>}

/>



<Route

path="profile"

element={<CompanyProfile/>}

/>



<Route

path="jobs"

element={<ManageJobs/>}

/>



<Route
path="jobs/create"
element={<CreateJob/>}
/>



<Route

path="candidates"

element={<Candidates/>}

/>


<Route

path="ai-assistant"

element={<CompanyAIAssistant/>}

/>


<Route

path="notifications"

element={<CompanyNotifications/>}

/>



<Route

path="interviews"

element={<Interview/>}

/>


<Route

path="analytics"

element={<CompanyAnalytics/>}

/>


<Route

path="results"

element={<SelectionResults/>}

/>


</Route>


</Route>













{/* =====================================================
                PLACEMENT ADMIN
===================================================== */}



<Route

path="/placement"

element={

<ProtectedRoute

allowedRoles={[

"placement_admin"

]}

/>

}

>


<Route element={<PlacementLayout/>}>


<Route

path="dashboard"

element={<PlacementDashboard/>}

/>



<Route

path="students"

element={<Students/>}

/>


<Route

path="students/add"

element={<AddEditStudent/>}

/>



<Route

path="companies"

element={<Companies/>}

/>



<Route

path="drives"

element={<Drives/>}

/>



<Route

path="interviews"

element={<PlacementInterviews/>}

/>


<Route

path="candidate-pipeline"

element={<CandidatePipeline/>}

/>


<Route

path="ai-chatbot"

element={<PlacementChatbot/>}

/>


<Route

path="job-listings"

element={<JobListings/>}

/>


<Route

path="resumes"

element={<ManageResumes/>}

/>


<Route

path="notifications"

element={<SendNotifications/>}

/>



<Route

path="reports"

element={<Reports/>}

/>



</Route>


</Route>













{/* =====================================================
                    CHATBOT TEST
===================================================== */}



<Route

path="/chat-test"

element={


<Chatbot/>


}

/>













{/* =====================================================
                    404
===================================================== */}



<Route

path="*"

element={

<NotFound/>

}


/>



</Routes>


</BrowserRouter>


);


}



export default App;
