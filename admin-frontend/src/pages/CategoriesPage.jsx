import { Navigate } from "react-router-dom";

export default function CategoriesPage() {
  return <Navigate to="/settings/chatbot?tab=categories" replace />;
}
