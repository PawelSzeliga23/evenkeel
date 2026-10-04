import { createContext, useContext } from "react";

export const PrivacyContext = createContext<[boolean, (hidden: boolean) => void]>([false, () => {}]);
export const usePrivacy = () => useContext(PrivacyContext);
