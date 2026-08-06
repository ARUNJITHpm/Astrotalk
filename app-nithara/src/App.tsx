import { useEffect, useRef } from 'react'
import { Route, Routes, useNavigate } from 'react-router-dom'
import { PhoneFrame } from './components/PhoneFrame'
import { TabBar } from './components/TabBar'
import { ToastHost } from './components/Toast'
import Home from './screens/Home'
import Poojas from './screens/Poojas'
import Astro from './screens/Astro'
import Profile from './screens/Profile'
import { enablePush } from './lib/native'

export default function App() {
  const navigate = useNavigate()
  const asked = useRef(false)

  // Register for push once per launch, on device only.
  //
  // Part 4 built the device-token store and the T-3 nakshatram reminder run,
  // and nothing ever registered a token — so the entire retention loop has
  // never delivered a notification to a real phone. This is its missing half.
  // On the web it returns 'unsupported' and does nothing: an FCM device token
  // is not the same mechanism as a browser push subscription, and registering
  // one that can never receive would be worse than not asking.
  useEffect(() => {
    if (asked.current) return
    asked.current = true
    void enablePush((data) => {
      // A star-day reminder is about a booking somebody may want to make.
      navigate(typeof data.route === 'string' ? data.route : '/poojas')
    })
  }, [navigate])

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
