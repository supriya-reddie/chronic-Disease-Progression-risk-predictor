import { Route, Routes } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Patients from "./pages/Patients.jsx";
import PatientDetail from "./pages/PatientDetail.jsx";
import RiskAnalytics from "./pages/RiskAnalytics.jsx";
import HighRiskPatients from "./pages/HighRiskPatients.jsx";
import CareManagement from "./pages/CareManagement.jsx";
import PredictionHistory from "./pages/PredictionHistory.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/patients" element={<Patients />} />
          <Route path="/patients/:patientId" element={<PatientDetail />} />
          <Route path="/risk-analytics" element={<RiskAnalytics />} />
          <Route path="/high-risk" element={<HighRiskPatients />} />
          <Route path="/care-management" element={<CareManagement />} />
          <Route path="/prediction-history" element={<PredictionHistory />} />
        </Routes>
      </div>
    </div>
  );
}
