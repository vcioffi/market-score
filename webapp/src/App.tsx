import { useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { TickerDetailPage } from "./pages/TickerDetailPage";

function App() {
  const [runDate, setRunDate] = useState<string | undefined>(undefined);

  return (
    <Layout runDate={runDate}>
      <Routes>
        <Route path="/" element={<DashboardPage onRunDateChange={setRunDate} />} />
        <Route path="/ticker/:symbol" element={<TickerDetailPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}

export default App;
