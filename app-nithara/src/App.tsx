import { Route, Routes } from 'react-router-dom'
import { PhoneFrame } from './components/PhoneFrame'
import { TabBar } from './components/TabBar'
import { ToastHost } from './components/Toast'
import Home from './screens/Home'
import Poojas from './screens/Poojas'
import Astro from './screens/Astro'
import Profile from './screens/Profile'

export default function App() {
  return (
    <PhoneFrame>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/poojas" element={<Poojas />} />
        <Route path="/astro" element={<Astro />} />
        <Route path="/profile" element={<Profile />} />
      </Routes>
      <TabBar />
      <ToastHost />
    </PhoneFrame>
  )
}
