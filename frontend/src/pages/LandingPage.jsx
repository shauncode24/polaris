import Navbar from '../components/layout/Navbar'
import Footer from '../components/layout/Footer'
import Hero from '../components/landing/Hero'
import FeatureCards from '../components/landing/FeatureCards'
import HowItWorks from '../components/landing/HowItWorks'
import ProfileDiagram from '../components/landing/ProfileDiagram'
import ClosingCta from '../components/landing/ClosingCta'

function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <FeatureCards />
        <HowItWorks />
        <ProfileDiagram />
        <ClosingCta />
      </main>
      <Footer />
    </>
  )
}

export default LandingPage
